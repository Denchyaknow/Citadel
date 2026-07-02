from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import asyncio
from pathlib import Path
from typing import Any

from starlette.responses import JSONResponse, StreamingResponse


LOCALBRAIN_MODEL_ID = 'localbrain-router:latest'
LOCALBRAIN_MODEL_NAME = 'LocalBrain'
LOCALBRAIN_PROVIDER = 'localbrain'


def ragstackproxy_root() -> Path:
    return Path(
        os.getenv('RAGSTACKPROXY_ROOT')
        or os.getenv('CITADEL_RAGSTACKPROXY_ROOT')
        or (Path.home() / 'RagStackProxy')
    ).resolve()


def localbrain_only_enabled() -> bool:
    value = os.getenv('CITADEL_LOCALBRAIN_ONLY') or os.getenv('HERMES_WEBUI_LOCALBRAIN_ONLY')
    if value is not None:
        return value.strip().lower() not in {'0', 'false', 'no', 'off', 'disabled'}
    return (ragstackproxy_root() / 'gateway' / 'citadel' / 'main.py').is_file()


def localbrain_model_catalog() -> list[dict[str, Any]]:
    return [
        {
            'id': LOCALBRAIN_MODEL_ID,
            'name': LOCALBRAIN_MODEL_NAME,
            'object': 'model',
            'created': 0,
            'owned_by': LOCALBRAIN_PROVIDER,
            'connection_type': LOCALBRAIN_PROVIDER,
            'info': {
                'meta': {
                    'capabilities': {
                        'chat': True,
                        'completion': True,
                        'embedding': False,
                        'tools': False,
                        'thinking': False,
                    },
                    'hidden': False,
                }
            },
            'tags': [{'name': LOCALBRAIN_MODEL_NAME}],
            'localbrain': {
                'root': str(ragstackproxy_root()),
                'selector': 'hidden',
            },
        }
    ]


def force_localbrain_form_data(form_data: dict[str, Any]) -> str | None:
    requested_model = form_data.get('localbrain_requested_model') or form_data.get('model')
    form_data['localbrain_requested_model'] = requested_model
    metadata = form_data.setdefault('metadata', {})
    if isinstance(metadata, dict):
        metadata.setdefault('requested_model', requested_model)
    form_data['model'] = LOCALBRAIN_MODEL_ID
    return requested_model if requested_model != LOCALBRAIN_MODEL_ID else None


def _load_citadel_contract():
    module_path = ragstackproxy_root() / 'gateway' / 'citadel' / 'main.py'
    spec = importlib.util.spec_from_file_location('ragstackproxy_citadel_contract', module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load RagStackProxy Citadel contract: {module_path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages or []):
        if message.get('role') != 'user':
            continue
        content = message.get('content', '')
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get('text')
                    if isinstance(text, str):
                        parts.append(text)
            return '\n'.join(parts)
    return ''


def _message_text(message: dict[str, Any]) -> str:
    content = message.get('content', '')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get('text')
                if isinstance(text, str):
                    parts.append(text)
        return '\n'.join(parts)
    return ''


def _conversation_context(messages: list[dict[str, Any]], latest_user_text: str, *, limit: int = 10) -> str:
    rows: list[str] = []
    for message in (messages or [])[-limit:]:
        role = str(message.get('role') or '').strip().lower()
        if role not in {'user', 'assistant', 'system'}:
            continue
        text = ' '.join(_message_text(message).split())
        if not text:
            continue
        if role == 'user' and text == latest_user_text:
            continue
        rows.append(f'{role}: {text[:900]}')
    return '\n'.join(rows)[-5000:]


def _completion_payload(completion_id: str, content: str, localbrain: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'id': completion_id,
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': LOCALBRAIN_MODEL_ID,
        'localbrain': localbrain or {},
        'choices': [
            {
                'index': 0,
                'message': {
                    'role': 'assistant',
                    'content': content,
                },
                'finish_reason': 'stop',
            }
        ],
    }


def _stream_chunk(completion_id: str, delta: dict[str, Any], finish_reason: str | None = None) -> str:
    payload = {
        'id': completion_id,
        'object': 'chat.completion.chunk',
        'created': int(time.time()),
        'model': LOCALBRAIN_MODEL_ID,
        'choices': [
            {
                'index': 0,
                'delta': delta,
                'finish_reason': finish_reason,
            }
        ],
    }
    return f'data: {json.dumps(payload)}\n\n'


async def generate_localbrain_chat_completion(request, form_data: dict[str, Any], user: Any):
    contract = _load_citadel_contract()
    messages = form_data.get('messages', [])
    prompt = _latest_user_text(messages)
    conversation_context = _conversation_context(messages, prompt)
    metadata = form_data.get('metadata', {}) if isinstance(form_data.get('metadata'), dict) else {}
    requested_model = metadata.get('requested_model') or form_data.get('localbrain_requested_model')
    user_id = str(getattr(user, 'id', None) or metadata.get('user_id') or 'citadel_user')
    if hasattr(contract, 'process_chat_message'):
        result = await asyncio.to_thread(
            contract.process_chat_message,
            prompt,
            user_id=user_id,
            selected_model=requested_model,
            conversation_context=conversation_context,
        )
        content = result.get('user_visible_answer') or 'LocalBrain completed the request.'
        debug = result.get('debug_drawer') or {}
        artifacts = result.get('artifacts') or {}
    else:
        selected_model, rejected_model = contract.resolve_chat_model(requested_model)
        route = contract.route_request(prompt)
        answer = contract.natural_answer(prompt, route)
        debug = contract.safe_debug_state(route, selected_model=selected_model, rejected_model=rejected_model)
        artifacts = {}
        content = answer if answer else 'LocalBrain completed the request.'
    localbrain = {'debug': debug, 'artifacts': artifacts}

    if form_data.get('stream'):
        completion_id = f'chatcmpl-localbrain-{int(time.time() * 1000)}'

        async def event_generator():
            yield _stream_chunk(completion_id, {'role': 'assistant'})
            yield _stream_chunk(completion_id, {'content': content})
            yield _stream_chunk(completion_id, {'localbrain': localbrain})
            yield _stream_chunk(completion_id, {}, finish_reason='stop')
            yield 'data: [DONE]\n\n'

        return StreamingResponse(event_generator(), media_type='text/event-stream')

    return JSONResponse(_completion_payload(f'chatcmpl-localbrain-{int(time.time() * 1000)}', content, localbrain))

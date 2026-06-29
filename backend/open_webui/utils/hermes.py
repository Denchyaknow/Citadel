from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

import aiohttp
from fastapi import HTTPException, Request, status
from open_webui.env import DATA_DIR
from starlette.responses import StreamingResponse

log = logging.getLogger(__name__)

HERMES_MODEL_PREFIX = 'hermes:'
HERMES_BASE_URL = os.getenv('CITADEL_HERMES_BASE_URL', 'http://127.0.0.1:8787').rstrip('/')
HERMES_PASSWORD = os.getenv('CITADEL_HERMES_PASSWORD', '').strip()
HERMES_TIMEOUT = float(os.getenv('CITADEL_HERMES_TIMEOUT', '600'))
HERMES_MAP_FILE = Path(DATA_DIR) / 'citadel_hermes_sessions.json'

_session_map_lock = asyncio.Lock()


def is_hermes_model_id(model_id: str | None) -> bool:
    return bool(model_id and str(model_id).startswith(HERMES_MODEL_PREFIX))


def hermes_profile_from_model(model_id: str | None) -> str:
    if not is_hermes_model_id(model_id):
        return 'default'
    profile = str(model_id)[len(HERMES_MODEL_PREFIX) :].strip()
    return profile or 'default'


def _timeout() -> aiohttp.ClientTimeout:
    return aiohttp.ClientTimeout(total=HERMES_TIMEOUT, connect=10)


async def _session() -> aiohttp.ClientSession:
    session = aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=True),
        timeout=_timeout(),
        trust_env=True,
    )
    if HERMES_PASSWORD:
        async with session.post(
            f'{HERMES_BASE_URL}/api/auth/login',
            json={'password': HERMES_PASSWORD},
            headers={'User-Agent': 'Citadel-Hermes-Backend/1.0'},
        ) as response:
            if response.status >= 400:
                text = await response.text()
                await session.close()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f'Hermes authentication failed: HTTP {response.status} {text[:200]}',
                )
    return session


async def hermes_json(method: str, path: str, **kwargs) -> Any:
    session = await _session()
    try:
        async with session.request(
            method,
            f'{HERMES_BASE_URL}{path}',
            headers={'User-Agent': 'Citadel-Hermes-Backend/1.0', **kwargs.pop('headers', {})},
            **kwargs,
        ) as response:
            text = await response.text()
            if response.status >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f'Hermes {path} failed: HTTP {response.status} {text[:400]}',
                )
            if not text:
                return {}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {'text': text}
    finally:
        await session.close()


async def hermes_health() -> dict[str, Any]:
    try:
        data = await hermes_json('GET', '/health')
        return {'ok': True, 'base_url': HERMES_BASE_URL, 'health': data}
    except Exception as exc:
        return {'ok': False, 'base_url': HERMES_BASE_URL, 'error': str(exc)}


async def hermes_profiles() -> dict[str, Any]:
    return await hermes_json('GET', '/api/profiles')


async def hermes_sessions() -> dict[str, Any]:
    return await hermes_json('GET', '/api/sessions')


async def hermes_skills() -> dict[str, Any]:
    return await hermes_json('GET', '/api/skills')


def _profile_name(profile: Any) -> str | None:
    if isinstance(profile, str):
        return profile.strip() or None
    if isinstance(profile, dict):
        for key in ('name', 'id', 'profile', 'slug'):
            value = str(profile.get(key) or '').strip()
            if value:
                return value
    return None


async def fetch_hermes_models(request: Request | None = None, user: Any = None) -> list[dict[str, Any]]:
    try:
        data = await hermes_profiles()
    except Exception as exc:
        log.warning('Unable to fetch Hermes profiles: %s', exc)
        return []

    profiles = data.get('profiles', []) if isinstance(data, dict) else []
    active = data.get('active') if isinstance(data, dict) else None
    names = sorted({name for name in (_profile_name(profile) for profile in profiles) if name})
    if not names:
        names = ['default']

    return [
        {
            'id': f'{HERMES_MODEL_PREFIX}{name}',
            'name': f'Hermes / {name}',
            'object': 'model',
            'created': 0,
            'owned_by': 'hermes',
            'connection_type': 'hermes',
            'hermes': {
                'profile': name,
                'active': name == active,
                'base_url': HERMES_BASE_URL,
            },
            'tags': [{'name': 'Hermes Agent'}],
        }
        for name in names
    ]


def _message_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ''
    content = message.get('content', '')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get('text') or part.get('content') or part.get('input_text') or ''))
        return '\n'.join(part for part in parts if part)
    return str(content or '')


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages or []):
        if isinstance(message, dict) and message.get('role') == 'user':
            text = _message_text(message).strip()
            if text:
                return text
    return ''


def _map_key(metadata: dict[str, Any], profile: str) -> str:
    chat_id = str(metadata.get('chat_id') or metadata.get('session_id') or '').strip()
    user_id = str(metadata.get('user_id') or '').strip()
    if not chat_id:
        chat_id = f'adhoc:{uuid.uuid4().hex}'
    return f'{user_id}:{profile}:{chat_id}'


async def _read_session_map() -> dict[str, str]:
    try:
        if HERMES_MAP_FILE.exists():
            data = json.loads(HERMES_MAP_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items() if v}
    except Exception:
        log.debug('Unable to read Hermes session map', exc_info=True)
    return {}


async def _write_session_map(data: dict[str, str]) -> None:
    try:
        HERMES_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = HERMES_MAP_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
        tmp.replace(HERMES_MAP_FILE)
    except Exception:
        log.debug('Unable to write Hermes session map', exc_info=True)


async def _get_or_create_hermes_session(
    client: aiohttp.ClientSession,
    *,
    metadata: dict[str, Any],
    profile: str,
    model: str | None,
) -> str:
    key = _map_key(metadata, profile)
    async with _session_map_lock:
        session_map = await _read_session_map()
        existing = session_map.get(key)
        if existing:
            return existing

        body = {'profile': profile}
        if model and not is_hermes_model_id(model):
            body['model'] = model
        async with client.post(f'{HERMES_BASE_URL}/api/session/new', json=body) as response:
            text = await response.text()
            if response.status >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f'Hermes session creation failed: HTTP {response.status} {text[:400]}',
                )
            payload = json.loads(text or '{}')
        hermes_session = payload.get('session') if isinstance(payload, dict) else None
        session_id = hermes_session.get('session_id') if isinstance(hermes_session, dict) else None
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail='Hermes session creation did not return a session_id',
            )
        session_map[key] = session_id
        await _write_session_map(session_map)
        return str(session_id)


def _openai_chunk(completion_id: str, model: str, content: str = '', *, role: bool = False, finish_reason=None) -> str:
    delta = {}
    if role:
        delta['role'] = 'assistant'
    if content:
        delta['content'] = content
    payload = {
        'id': completion_id,
        'object': 'chat.completion.chunk',
        'created': int(time.time()),
        'model': model,
        'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish_reason}],
    }
    return f'data: {json.dumps(payload, ensure_ascii=False)}\n\n'


def _openai_message(completion_id: str, model: str, content: str) -> dict[str, Any]:
    return {
        'id': completion_id,
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': model,
        'choices': [
            {
                'index': 0,
                'message': {'role': 'assistant', 'content': content},
                'finish_reason': 'stop',
            }
        ],
    }


def _sse_payload_text(event: str, payload: dict[str, Any]) -> str:
    if event in {'token', 'reasoning'}:
        return str(payload.get('text') or '')
    if event == 'interim_assistant':
        text = str(payload.get('text') or '')
        return f'\n\n{text}' if text else ''
    for key in ('delta', 'text', 'content', 'message', 'output'):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ''


async def _hermes_event_stream(
    client: aiohttp.ClientSession,
    *,
    stream_id: str,
    completion_id: str,
    model_id: str,
):
    yield _openai_chunk(completion_id, model_id, role=True)
    async with client.get(f'{HERMES_BASE_URL}/api/chat/stream', params={'stream_id': stream_id}) as response:
        if response.status >= 400:
            text = await response.text()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f'Hermes stream failed: HTTP {response.status} {text[:400]}',
            )
        event = 'message'
        data_lines: list[str] = []
        async for raw in response.content:
            line = raw.decode('utf-8', 'replace').rstrip('\r\n')
            if not line:
                if data_lines:
                    raw_data = '\n'.join(data_lines)
                    data_lines = []
                    try:
                        payload = json.loads(raw_data)
                    except json.JSONDecodeError:
                        payload = {'text': raw_data}
                    if event in {'done', 'stream_end', 'cancel'}:
                        break
                    if event in {'error', 'apperror'}:
                        error_text = str(payload.get('message') or payload.get('error') or payload)
                        yield _openai_chunk(completion_id, model_id, f'\n\n**Hermes error:** {error_text}')
                        break
                    text = _sse_payload_text(event, payload if isinstance(payload, dict) else {'text': payload})
                    if text:
                        yield _openai_chunk(completion_id, model_id, text)
                event = 'message'
                continue
            if line.startswith(':'):
                continue
            if line.startswith('event:'):
                event = line.split(':', 1)[1].strip() or 'message'
            elif line.startswith('data:'):
                data_lines.append(line.split(':', 1)[1].lstrip())
    yield _openai_chunk(completion_id, model_id, finish_reason='stop')
    yield 'data: [DONE]\n\n'


async def _start_hermes_turn(
    client: aiohttp.ClientSession,
    *,
    session_id: str,
    profile: str,
    prompt: str,
    form_data: dict[str, Any],
) -> str:
    metadata = form_data.get('metadata') or {}
    body = {
        'session_id': session_id,
        'message': prompt,
        'profile': profile,
    }
    if metadata.get('files'):
        body['attachments'] = metadata.get('files')
    async with client.post(f'{HERMES_BASE_URL}/api/chat/start', json=body) as response:
        text = await response.text()
        if response.status >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f'Hermes chat start failed: HTTP {response.status} {text[:400]}',
            )
        payload = json.loads(text or '{}')
    stream_id = payload.get('stream_id') if isinstance(payload, dict) else None
    if not stream_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Hermes chat start did not return a stream_id',
        )
    return str(stream_id)


async def generate_hermes_chat_completion(request: Request, form_data: dict[str, Any], user: Any) -> Any:
    model_id = form_data.get('model')
    profile = hermes_profile_from_model(model_id)
    messages = form_data.get('messages') or []
    prompt = _latest_user_text(messages)
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Hermes chat requires a user message')

    completion_id = f'chatcmpl-hermes-{uuid.uuid4().hex}'
    client = await _session()
    try:
        session_id = await _get_or_create_hermes_session(
            client,
            metadata=form_data.get('metadata') or {},
            profile=profile,
            model=model_id,
        )
        stream_id = await _start_hermes_turn(
            client,
            session_id=session_id,
            profile=profile,
            prompt=prompt,
            form_data=form_data,
        )

        if form_data.get('stream', False):

            async def stream():
                try:
                    async for chunk in _hermes_event_stream(
                        client,
                        stream_id=stream_id,
                        completion_id=completion_id,
                        model_id=model_id,
                    ):
                        yield chunk
                finally:
                    await client.close()

            return StreamingResponse(
                stream(),
                media_type='text/event-stream',
                headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'},
            )

        chunks: list[str] = []
        async for chunk in _hermes_event_stream(
            client,
            stream_id=stream_id,
            completion_id=completion_id,
            model_id=model_id,
        ):
            if not chunk.startswith('data: ') or chunk.strip() == 'data: [DONE]':
                continue
            try:
                payload = json.loads(chunk[6:])
                content = payload.get('choices', [{}])[0].get('delta', {}).get('content')
                if content:
                    chunks.append(content)
            except Exception:
                pass
        await client.close()
        return _openai_message(completion_id, model_id, ''.join(chunks))
    except Exception:
        await client.close()
        raise

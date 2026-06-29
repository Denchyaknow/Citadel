from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import aiohttp
from fastapi import HTTPException, Request, status
from open_webui.env import DATA_DIR
from open_webui.internal.db import get_async_db_context
from open_webui.models.chats import Chat, ChatModel
from starlette.responses import StreamingResponse

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency guard
    yaml = None

log = logging.getLogger(__name__)

HERMES_MODEL_PREFIX = 'hermes:'
HERMES_MODEL_OVERRIDE_SEP = '#model='
HERMES_BASE_URL = os.getenv('CITADEL_HERMES_BASE_URL', 'http://127.0.0.1:8787').rstrip('/')
HERMES_PASSWORD = os.getenv('CITADEL_HERMES_PASSWORD', '').strip()
HERMES_TIMEOUT = float(os.getenv('CITADEL_HERMES_TIMEOUT', '600'))
HERMES_SYNC_TIMEOUT = float(os.getenv('CITADEL_HERMES_SYNC_TIMEOUT', '8'))
HERMES_MAP_FILE = Path(DATA_DIR) / 'citadel_hermes_sessions.json'

_session_map_lock = asyncio.Lock()


def is_hermes_model_id(model_id: str | None) -> bool:
    return bool(model_id and str(model_id).startswith(HERMES_MODEL_PREFIX))


def hermes_profile_from_model(model_id: str | None) -> str:
    if not is_hermes_model_id(model_id):
        return 'default'
    profile = str(model_id)[len(HERMES_MODEL_PREFIX) :].split(HERMES_MODEL_OVERRIDE_SEP, 1)[0].strip()
    return profile or 'default'


def hermes_model_id_for_profile(profile: str | None) -> str:
    return f'{HERMES_MODEL_PREFIX}{(profile or "default").strip() or "default"}'


def hermes_model_override_from_model(model_id: str | None) -> str | None:
    if not is_hermes_model_id(model_id):
        return None
    value = str(model_id)
    if HERMES_MODEL_OVERRIDE_SEP not in value:
        return None
    override = unquote(value.split(HERMES_MODEL_OVERRIDE_SEP, 1)[1].strip())
    return override or None


def display_profile_name(value: str | None) -> str:
    words = re.findall(r'[A-Za-z0-9]+', re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', value or 'default'))
    return ''.join(word[:1].upper() + word[1:].lower() for word in words) or 'Default'


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
            headers={'User-Agent': 'Citadel-Backend/1.0'},
        ) as response:
            if response.status >= 400:
                text = await response.text()
                await session.close()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f'Agent service authentication failed: HTTP {response.status} {text[:200]}',
                )
    return session


async def hermes_json(method: str, path: str, *, request_timeout: float | None = None, **kwargs) -> Any:
    session = await _session()
    try:
        if request_timeout is not None:
            kwargs['timeout'] = aiohttp.ClientTimeout(total=request_timeout, connect=min(request_timeout, 3))
        async with session.request(
            method,
            f'{HERMES_BASE_URL}{path}',
            headers={'User-Agent': 'Citadel-Backend/1.0', **kwargs.pop('headers', {})},
            **kwargs,
        ) as response:
            text = await response.text()
            if response.status >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f'Agent service {path} failed: HTTP {response.status} {text[:400]}',
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


async def hermes_sessions(*, request_timeout: float | None = None) -> dict[str, Any]:
    return await hermes_json('GET', '/api/sessions?all_profiles=1', request_timeout=request_timeout)


async def hermes_session(session_id: str, *, request_timeout: float | None = None) -> dict[str, Any]:
    return await hermes_json('GET', f'/api/session?session_id={quote(session_id)}', request_timeout=request_timeout)


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


def _profile_fallback_models(profile: Any) -> list[dict[str, Any]]:
    if not isinstance(profile, dict) or yaml is None:
        return []
    path = str(profile.get('path') or '').strip()
    if not path:
        return []
    config_path = Path(path).expanduser() / 'config.yaml'
    try:
        config = yaml.safe_load(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    except Exception:
        log.debug('Unable to read agent profile config at %s', config_path, exc_info=True)
        return []
    fallback_providers = config.get('fallback_providers', []) if isinstance(config, dict) else []
    if not isinstance(fallback_providers, list):
        return []

    fallbacks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, entry in enumerate(fallback_providers, start=1):
        if not isinstance(entry, dict):
            continue
        model = str(entry.get('model') or '').strip()
        if not model or model in seen:
            continue
        seen.add(model)
        provider = str(entry.get('provider') or '').strip()
        fallbacks.append(
            {
                'id': model,
                'name': model,
                'provider': provider or None,
                'label': f'Fallback {idx}',
            }
        )
    return fallbacks


async def fetch_hermes_models(request: Request | None = None, user: Any = None) -> list[dict[str, Any]]:
    try:
        data = await hermes_profiles()
    except Exception as exc:
        log.warning('Unable to fetch agent profiles: %s', exc)
        return []

    profiles = data.get('profiles', []) if isinstance(data, dict) else []
    active = data.get('active') if isinstance(data, dict) else None
    names = sorted({name for name in (_profile_name(profile) for profile in profiles) if name})
    if not names:
        names = ['default']

    items = []
    profile_by_name = {(_profile_name(profile) or ''): profile for profile in profiles}
    for name in names:
        profile = profile_by_name.get(name, {})
        fallbacks = _profile_fallback_models(profile)
        display_name = display_profile_name(name)
        items.append({
            'id': f'{HERMES_MODEL_PREFIX}{name}',
            'name': display_name,
            'object': 'model',
            'created': 0,
            'owned_by': 'hermes',
            'connection_type': 'hermes',
            'hermes': {
                'profile': name,
                'active': name == active,
                'base_url': HERMES_BASE_URL,
                'fallbacks': fallbacks,
            },
            'tags': [{'name': 'Agent'}],
        })
    return items


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


def _as_epoch_seconds(value: Any, fallback: int | None = None) -> int:
    if fallback is None:
        fallback = int(time.time())
    try:
        number = float(value)
        if number > 10_000_000_000:
            number = number / 1000
        return int(number)
    except Exception:
        return fallback


def _hermes_session_profile(session: dict[str, Any]) -> str:
    profile = str(session.get('profile') or session.get('active_profile') or '').strip()
    return profile or 'default'


def _hermes_chat_id(user_id: str, hermes_session_id: str) -> str:
    digest = hashlib.sha256(f'{user_id}:{hermes_session_id}'.encode('utf-8')).hexdigest()[:32]
    return f'hermes-{digest}'


def _message_id(session_id: str, index: int, message: dict[str, Any]) -> str:
    existing = str(message.get('id') or message.get('message_id') or '').strip()
    if existing:
        return existing
    digest = hashlib.sha1(
        f'{session_id}:{index}:{message.get("role")}:{message.get("timestamp")}:{_message_text(message)}'.encode(
            'utf-8', 'ignore'
        )
    ).hexdigest()[:24]
    return f'hermes-msg-{digest}'


def _title_from_hermes_session(session: dict[str, Any]) -> str:
    title = str(session.get('title') or '').strip()
    if title:
        return title
    for message in session.get('messages') or []:
        if isinstance(message, dict) and message.get('role') == 'user':
            text = _message_text(message).strip()
            if text:
                return text[:60]
    return 'AgentSession'


def _session_detail_from_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    wrapped = payload.get('session')
    if isinstance(wrapped, dict):
        return wrapped
    if payload.get('session_id'):
        return payload
    return None


def _messages_to_openwebui_history(
    session_id: str,
    messages: list[dict[str, Any]],
    model_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    history_messages: dict[str, Any] = {}
    ordered: list[dict[str, Any]] = []
    previous_id: str | None = None

    for index, raw in enumerate(messages or []):
        if not isinstance(raw, dict):
            continue
        role = str(raw.get('role') or '').strip()
        if role not in {'user', 'assistant', 'system'}:
            continue
        content = _message_text(raw).strip()
        if not content and role != 'assistant':
            continue

        message_id = _message_id(session_id, index, raw)
        message = {
            'id': message_id,
            'parentId': previous_id,
            'childrenIds': [],
            'role': role,
            'content': content,
            'timestamp': _as_epoch_seconds(raw.get('timestamp') or raw.get('created_at')),
        }
        if role == 'assistant':
            message['model'] = model_id
            message['done'] = True
        if previous_id and previous_id in history_messages:
            history_messages[previous_id]['childrenIds'] = [message_id]
        history_messages[message_id] = message
        ordered.append(message)
        previous_id = message_id

    return {'messages': history_messages, 'currentId': previous_id}, ordered


def _chat_payload_from_hermes_session(
    *,
    chat_id: str,
    session: dict[str, Any],
    user: Any,
) -> dict[str, Any]:
    hermes_session_id = str(session.get('session_id') or '').strip()
    profile = _hermes_session_profile(session)
    model_id = hermes_model_id_for_profile(profile)
    title = _title_from_hermes_session(session)
    created_at = _as_epoch_seconds(session.get('created_at') or session.get('started_at'))
    updated_at = _as_epoch_seconds(
        session.get('updated_at') or session.get('last_message_at') or session.get('created_at'),
        fallback=created_at,
    )
    history, messages = _messages_to_openwebui_history(
        hermes_session_id,
        session.get('messages') if isinstance(session.get('messages'), list) else [],
        model_id,
    )
    return {
        'id': chat_id,
        'title': title,
        'models': [model_id],
        'params': {},
        'history': history,
        'messages': messages,
        'tags': [],
        'timestamp': updated_at * 1000,
        'hermes': {
            'session_id': hermes_session_id,
            'profile': profile,
            'workspace': session.get('workspace'),
            'source': session.get('source') or session.get('session_source') or 'hermes',
            'model': session.get('model'),
            'model_provider': session.get('model_provider'),
            'citadel_user': {
                'id': getattr(user, 'id', None),
                'name': getattr(user, 'name', None),
                'email': getattr(user, 'email', None),
                'role': getattr(user, 'role', None),
            },
        },
        '_created_at': created_at,
        '_updated_at': updated_at,
    }


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
        log.debug('Unable to read agent session map', exc_info=True)
    return {}


def _mapped_chat_for_hermes_session(
    session_map: dict[str, str],
    *,
    user_id: str,
    profile: str,
    hermes_session_id: str,
) -> str | None:
    prefix = f'{user_id}:{profile}:'
    for key, value in session_map.items():
        if value == hermes_session_id and key.startswith(prefix):
            chat_id = key[len(prefix) :].strip()
            if chat_id:
                return chat_id
    return None


def _remember_hermes_mapping(
    session_map: dict[str, str],
    *,
    user_id: str,
    profile: str,
    chat_id: str,
    hermes_session_id: str,
) -> None:
    session_map[f'{user_id}:{profile}:{chat_id}'] = hermes_session_id


async def _write_session_map(data: dict[str, str]) -> None:
    try:
        HERMES_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = HERMES_MAP_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
        tmp.replace(HERMES_MAP_FILE)
    except Exception:
        log.debug('Unable to write agent session map', exc_info=True)


async def _upsert_hermes_chat_shadow(
    *,
    user: Any,
    chat_id: str,
    session: dict[str, Any],
    db=None,
) -> ChatModel | None:
    payload = _chat_payload_from_hermes_session(chat_id=chat_id, session=session, user=user)
    created_at = payload.pop('_created_at')
    updated_at = payload.pop('_updated_at')
    meta = {
        'source': 'hermes',
        'hermes_session_id': payload['hermes']['session_id'],
        'hermes_profile': payload['hermes']['profile'],
        'tags': ['agent'],
    }

    async with get_async_db_context(db) as session_db:
        row = await session_db.get(Chat, chat_id)
        if row and row.user_id != getattr(user, 'id', None):
            return None
        if row:
            has_session_messages = isinstance(session.get('messages'), list)
            if has_session_messages:
                row.title = payload['title']
                row.chat = payload
            else:
                existing_payload = row.chat if isinstance(row.chat, dict) else {}
                existing_hermes = existing_payload.get('hermes') if isinstance(existing_payload, dict) else {}
                row.chat = {
                    **existing_payload,
                    'hermes': {
                        **(existing_hermes if isinstance(existing_hermes, dict) else {}),
                        **payload['hermes'],
                    },
                }
                if not row.title or row.title == 'New Chat':
                    row.title = payload['title']
            row.meta = {**(row.meta or {}), **meta}
            row.updated_at = max(row.updated_at or 0, updated_at)
            if not row.created_at:
                row.created_at = created_at
        else:
            row = Chat(
                id=chat_id,
                user_id=getattr(user, 'id', ''),
                title=payload['title'],
                chat=payload,
                meta=meta,
                folder_id=None,
                archived=False,
                pinned=False,
                created_at=created_at,
                updated_at=updated_at,
            )
            session_db.add(row)
        await session_db.commit()
        await session_db.refresh(row)
        return ChatModel.model_validate(row)


async def sync_hermes_sessions_to_chats(
    user: Any, *, db=None, limit: int = 80, hydrate_details: bool = False
) -> list[dict[str, Any]]:
    data = await hermes_sessions(request_timeout=HERMES_SYNC_TIMEOUT)
    sessions = data.get('sessions', []) if isinstance(data, dict) else []
    if not isinstance(sessions, list):
        return []

    user_id = str(getattr(user, 'id', '') or '')
    synced: list[dict[str, Any]] = []
    async with _session_map_lock:
        session_map = await _read_session_map()
        for compact in sessions[:limit]:
            if not isinstance(compact, dict):
                continue
            hermes_session_id = str(compact.get('session_id') or '').strip()
            if not hermes_session_id:
                continue
            profile = _hermes_session_profile(compact)
            chat_id = _mapped_chat_for_hermes_session(
                session_map,
                user_id=user_id,
                profile=profile,
                hermes_session_id=hermes_session_id,
            ) or _hermes_chat_id(user_id, hermes_session_id)

            detail = compact
            if hydrate_details and not isinstance(compact.get('messages'), list):
                try:
                    detail_payload = await hermes_session(hermes_session_id, request_timeout=HERMES_SYNC_TIMEOUT)
                    detail_session = _session_detail_from_payload(detail_payload)
                    if isinstance(detail_session, dict):
                        detail = {**compact, **detail_session}
                except Exception:
                    log.debug('Unable to hydrate agent session %s during sync', hermes_session_id, exc_info=True)

            chat = await _upsert_hermes_chat_shadow(user=user, chat_id=chat_id, session=detail, db=db)
            if chat:
                _remember_hermes_mapping(
                    session_map,
                    user_id=user_id,
                    profile=profile,
                    chat_id=chat_id,
                    hermes_session_id=hermes_session_id,
                )
                synced.append(
                    {
                        'chat_id': chat.id,
                        'hermes_session_id': hermes_session_id,
                        'profile': profile,
                        'title': chat.title,
                    }
                )
        await _write_session_map(session_map)
    return synced


async def hydrate_hermes_chat(chat: ChatModel, user: Any, *, db=None) -> ChatModel:
    hermes_meta = (chat.chat or {}).get('hermes') if isinstance(chat.chat, dict) else None
    hermes_session_id = str((hermes_meta or {}).get('session_id') or '').strip()
    if not hermes_session_id:
        return chat
    try:
        detail_payload = await hermes_session(hermes_session_id, request_timeout=HERMES_SYNC_TIMEOUT)
        detail = _session_detail_from_payload(detail_payload)
        if not isinstance(detail, dict):
            return chat
        profile = _hermes_session_profile(detail)
        async with _session_map_lock:
            session_map = await _read_session_map()
            _remember_hermes_mapping(
                session_map,
                user_id=str(getattr(user, 'id', '') or ''),
                profile=profile,
                chat_id=chat.id,
                hermes_session_id=hermes_session_id,
            )
            await _write_session_map(session_map)
        updated = await _upsert_hermes_chat_shadow(user=user, chat_id=chat.id, session=detail, db=db)
        return updated or chat
    except Exception:
        log.debug('Unable to hydrate agent chat %s from session %s', chat.id, hermes_session_id, exc_info=True)
        return chat


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
                    detail=f'Agent session creation failed: HTTP {response.status} {text[:400]}',
                )
            payload = json.loads(text or '{}')
        hermes_session = payload.get('session') if isinstance(payload, dict) else None
        session_id = hermes_session.get('session_id') if isinstance(hermes_session, dict) else None
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail='Agent session creation did not return a session_id',
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
                detail=f'Agent stream failed: HTTP {response.status} {text[:400]}',
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
                        yield _openai_chunk(completion_id, model_id, f'\n\n**Agent error:** {error_text}')
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
    model_override = hermes_model_override_from_model(str(form_data.get('model') or ''))
    if model_override:
        body['model'] = model_override
    if metadata.get('files'):
        body['attachments'] = metadata.get('files')
    citadel_context = {
        'source': 'citadel',
        'user': metadata.get('citadel_user'),
        'chat_id': metadata.get('chat_id'),
        'folder_id': metadata.get('folder_id'),
        'workspace': metadata.get('workspace'),
    }
    body['citadel_context'] = citadel_context
    async with client.post(f'{HERMES_BASE_URL}/api/chat/start', json=body) as response:
        text = await response.text()
        if response.status >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f'Agent chat start failed: HTTP {response.status} {text[:400]}',
            )
        payload = json.loads(text or '{}')
    stream_id = payload.get('stream_id') if isinstance(payload, dict) else None
    if not stream_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Agent chat start did not return a stream_id',
        )
    return str(stream_id)


async def generate_hermes_chat_completion(request: Request, form_data: dict[str, Any], user: Any) -> Any:
    model_id = form_data.get('model')
    profile = hermes_profile_from_model(model_id)
    messages = form_data.get('messages') or []
    prompt = _latest_user_text(messages)
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Agent chat requires a user message')

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

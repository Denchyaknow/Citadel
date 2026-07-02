from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
from typing import Any

import aiohttp
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
import yaml


router = APIRouter()

RAGSTACK_ROOT = Path(os.getenv('CITADEL_RAGSTACKPROXY_ROOT', Path.home() / 'RagStackProxy')).resolve()
FRONTGATE_URL = os.getenv('CITADEL_RAGSTACKPROXY_FRONTGATE_URL', 'http://127.0.0.1:8000/route').strip()
OUTBOUNDGATE_URL = os.getenv('CITADEL_RAGSTACKPROXY_OUTBOUNDGATE_URL', 'http://127.0.0.1:8001/handoff').strip()
RAGSTACK_TOKEN = os.getenv('CITADEL_RAGSTACKPROXY_TOKEN', '').strip()
REQUEST_TIMEOUT = float(os.getenv('CITADEL_RAGSTACKPROXY_TIMEOUT', '15'))

MEMORY_DIR = RAGSTACK_ROOT / 'vault' / '20_MemoryCards'
APPROVAL_DIR = RAGSTACK_ROOT / 'runtime' / 'approval_queue'
HANDOFF_DIR = RAGSTACK_ROOT / 'vault' / '30_HandoffRecords'
RUNTIME_HANDOFF_DIR = RAGSTACK_ROOT / 'runtime' / 'handoff_records'
CHAT_LOG_DIR = RAGSTACK_ROOT / 'vaults' / 'LocalBrain' / '10_RawInbox' / 'ChatLogs'
CLOUD_RETURN_DIR = RAGSTACK_ROOT / 'vaults' / 'LocalBrain' / '10_RawInbox' / 'CloudBrainReturns'
PRIVACY_CHOICES = RAGSTACK_ROOT / 'runtime' / 'privacy_coach' / 'choices.json'


class FrontmatterLoader(yaml.SafeLoader):
    pass


FrontmatterLoader.yaml_implicit_resolvers = {
    key: list(value)
    for key, value in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
for first_char, resolvers in list(FrontmatterLoader.yaml_implicit_resolvers.items()):
    FrontmatterLoader.yaml_implicit_resolvers[first_char] = [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != 'tag:yaml.org,2002:timestamp'
    ]


class ChatRequest(BaseModel):
    user: str = Field('citadel_user', min_length=1, max_length=80)
    message: str = Field(..., min_length=1, max_length=4000)
    company_id: str = Field('BaseCompany', min_length=1, max_length=120)
    role: str = Field('StandardUser', min_length=1, max_length=120)
    provider: str = Field('public_web', min_length=1, max_length=120)
    memory_ids: list[str] = Field(default_factory=list)
    session_id: str = Field('citadel-session', max_length=160)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


async def require_ragstackproxy_token(
    authorization: str | None = Header(default=None),
    x_ragstackproxy_token: str | None = Header(default=None),
) -> None:
    if not RAGSTACK_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='RagStackProxy token is not configured for Citadel',
        )
    bearer = ''
    if authorization:
        scheme, _, token = authorization.partition(' ')
        if scheme.lower() == 'bearer':
            bearer = token
    supplied = x_ragstackproxy_token or bearer
    if not supplied or not secrets.compare_digest(supplied, RAGSTACK_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='authentication_required')


async def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT, connect=min(REQUEST_TIMEOUT, 5))
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.post(url, json=payload, headers={'User-Agent': 'Citadel-RagStackProxy/1.0'}) as response:
                text = await response.text()
                if response.status >= 400:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={'upstream_status': response.status, 'upstream_body': text[:500]},
                    )
                try:
                    data = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='upstream returned non-JSON') from exc
    except HTTPException:
        raise
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail={'upstream_timeout': url}) from exc
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={'upstream_error': repr(exc)}) from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='upstream returned non-object JSON')
    return data


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        return {}, text
    parts = text.split('---\n', 2)
    if len(parts) != 3:
        return {}, text
    metadata = yaml.load(parts[1], Loader=FrontmatterLoader) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata, parts[2].strip()


def safe_memory_summary(path: Path) -> dict[str, Any]:
    metadata, body = parse_frontmatter(path)
    privacy_class = str(metadata.get('privacy_class', 'local_only'))
    is_local_only = privacy_class == 'local_only'
    return {
        'id': str(metadata.get('id', path.stem)),
        'title': str(metadata.get('title', path.stem)),
        'company_id': str(metadata.get('company_id', '')),
        'privacy_class': privacy_class,
        'trust_class': str(metadata.get('trust_class', '')),
        'requires_approval': bool(metadata.get('requires_approval', False)),
        'path': str(path.relative_to(RAGSTACK_ROOT)),
        'safe_summary': '[local_only memory hidden by Citadel]' if is_local_only else ' '.join(body.split())[:360],
    }


def memory_summaries() -> list[dict[str, Any]]:
    if not MEMORY_DIR.exists():
        return []
    return [safe_memory_summary(path) for path in sorted(MEMORY_DIR.rglob('*.md'))]


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {'_error': 'unreadable_json', 'path': str(path)}
    return data if isinstance(data, dict) else {'_error': 'not_object', 'path': str(path)}


def approval_summary(path: Path, state: str) -> dict[str, Any]:
    data = load_json_file(path)
    return {
        'request_id': str(data.get('request_id', path.stem)),
        'state': state,
        'provider': str(data.get('provider', '')),
        'company_id': str(data.get('company_id', '')),
        'purpose': str(data.get('purpose', '')),
        'memory_ids': [str(item) for item in data.get('memory_ids', []) if isinstance(item, str)],
        'risk_reasons': [str(item) for item in data.get('risk_reasons', [])[:8]],
        'created_utc': str(data.get('created_utc', '')),
        'decided_utc': str(data.get('decided_utc', '')),
        'path': str(path.relative_to(RAGSTACK_ROOT)),
    }


def approval_summaries() -> dict[str, Any]:
    result: dict[str, Any] = {'pending': [], 'approved': [], 'rejected': []}
    for state_name in result:
        directory = APPROVAL_DIR / state_name
        if directory.exists():
            result[state_name] = [approval_summary(path, state_name) for path in sorted(directory.glob('*.json'))]
    result['counts'] = {state_name: len(items) for state_name, items in result.items() if isinstance(items, list)}
    return result


def handoff_summary(path: Path, direction: str) -> dict[str, Any]:
    data = load_json_file(path)
    payload = data.get('payload', {}) if isinstance(data.get('payload'), dict) else {}
    return {
        'direction': direction,
        'record_type': str(data.get('record_type', '')),
        'payload_hash': str(data.get('payload_hash', '')),
        'sent_payload_hash': str(data.get('sent_payload_hash', '')),
        'provider': str(payload.get('provider', '')),
        'request_id': str(payload.get('request_id', path.stem)),
        'memory_ids_requested': [str(item) for item in payload.get('memory_ids_requested', []) if isinstance(item, str)],
        'memory_ids_sent': [str(item) for item in payload.get('memory_ids_sent', []) if isinstance(item, str)],
        'return_scan': data.get('return_scan', {}) if isinstance(data.get('return_scan'), dict) else {},
        'redactions': [str(item) for item in data.get('redactions', [])[:12]],
        'path': str(path.relative_to(RAGSTACK_ROOT)),
    }


def handoff_summaries(limit: int = 20) -> dict[str, Any]:
    sent_dir = HANDOFF_DIR / 'SentPayloads'
    returned_dir = HANDOFF_DIR / 'ReturnedPayloads'
    sent = [handoff_summary(path, 'sent') for path in sorted(sent_dir.glob('*.json'))[-limit:]] if sent_dir.exists() else []
    returned = [handoff_summary(path, 'returned') for path in sorted(returned_dir.glob('*.json'))[-limit:]] if returned_dir.exists() else []
    return {'sent': sent, 'returned': returned, 'counts': {'sent': len(sent), 'returned': len(returned)}}


def compact_text(value: Any, limit: int = 900) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else f'{text[:limit - 3]}...'


def handoff_exchange_text(handoff: dict[str, Any], route: dict[str, Any], chat: dict[str, Any]) -> str:
    if not handoff:
        return ''
    allowed_tools = handoff.get('allowed_tools', []) if isinstance(handoff.get('allowed_tools'), list) else []
    memory_sent = handoff.get('memory_ids_sent', []) if isinstance(handoff.get('memory_ids_sent'), list) else []
    parts = [
        f"route={route.get('route') or route.get('name') or ''}",
        f"task_type={handoff.get('task_type') or 'unknown'}",
        f"request_id={handoff.get('request_id') or chat.get('request_id') or ''}",
        f"task_package_hash={handoff.get('task_package_hash') or ''}",
        f"allowed_tools={', '.join(str(item) for item in allowed_tools) or '-'}",
        f"memory_sent={', '.join(str(item) for item in memory_sent) or '-'}",
        f"redactions={handoff.get('redaction_count', 0) or 0}",
        f"approval={handoff.get('approval_state') or '-'}",
    ]
    return ' | '.join(parts)


def brain_exchange_summary(path: Path) -> dict[str, Any]:
    chat = load_json_file(path)
    request_id = str(chat.get('request_id', path.stem))
    handoff_path = RUNTIME_HANDOFF_DIR / f'{request_id}.json'
    cloud_return_path = CLOUD_RETURN_DIR / f'{request_id}.json'
    handoff = load_json_file(handoff_path) if handoff_path.is_file() else {}
    cloud_return = load_json_file(cloud_return_path) if cloud_return_path.is_file() else {}
    cloud_result = cloud_return.get('cloud_result', {}) if isinstance(cloud_return.get('cloud_result'), dict) else {}
    route = chat.get('route', {}) if isinstance(chat.get('route'), dict) else {}
    debug = chat.get('debug', {}) if isinstance(chat.get('debug'), dict) else {}
    cloud_debug = debug.get('cloudbrain', {}) if isinstance(debug.get('cloudbrain'), dict) else {}
    memory_debug = debug.get('memory', {}) if isinstance(debug.get('memory'), dict) else {}
    debug_created = memory_debug.get('created_ids', []) if isinstance(memory_debug.get('created_ids', []), list) else []
    debug_used = memory_debug.get('used_ids', []) if isinstance(memory_debug.get('used_ids', []), list) else []
    handoff_created = handoff.get('memory_cards_created', []) if isinstance(handoff.get('memory_cards_created', []), list) else []
    return_created = cloud_return.get('memory_cards_created', []) if isinstance(cloud_return.get('memory_cards_created', []), list) else []
    created_ids = [str(item) for item in debug_created]
    for item in [*handoff_created, *return_created]:
        if isinstance(item, dict) and item.get('memory_id'):
            created_ids.append(str(item['memory_id']))
        elif isinstance(item, str):
            created_ids.append(item)
    created_ids = list(dict.fromkeys(created_ids))
    used_ids = list(dict.fromkeys(str(item) for item in debug_used))
    return {
        'created': str(chat.get('created', '')),
        'request_id': request_id,
        'route': str(route.get('route') or route.get('name') or ''),
        'cloudbrain_invoked': bool(
            (handoff and not handoff.get('cloudbrain_invocation_skipped', True))
            or cloud_debug.get('invoked')
        ),
        'cloudbrain_status': str(handoff.get('provider_status') or cloud_result.get('status') or ''),
        'task_type': str(handoff.get('task_type', '')),
        'allowed_tools': handoff.get('allowed_tools', []) if isinstance(handoff.get('allowed_tools', []), list) else [],
        'tools_used': handoff.get('tools_used', cloud_result.get('tools_used', [])) if isinstance(handoff.get('tools_used', cloud_result.get('tools_used', [])), list) else [],
        'redaction_count': int(handoff.get('redaction_count', 0) or 0),
        'return_allowed': (cloud_return.get('scan') or {}).get('allowed') if isinstance(cloud_return.get('scan'), dict) else None,
        'memory_used': bool(used_ids),
        'memory_created': bool(created_ids),
        'memory_used_ids': used_ids,
        'memory_created_ids': created_ids,
        'user_to_localbrain': compact_text(chat.get('message')),
        'localbrain_to_cloudbrain': compact_text(handoff_exchange_text(handoff, route, chat)),
        'cloudbrain_to_localbrain': compact_text(cloud_result.get('user_visible_answer')),
        'cloudbrain_work_summary': compact_text(cloud_result.get('work_summary')),
        'localbrain_to_user': compact_text(chat.get('response')),
        'paths': {
            'chat_log': str(path.relative_to(RAGSTACK_ROOT)),
            'handoff': str(handoff_path.relative_to(RAGSTACK_ROOT)) if handoff_path.is_file() else None,
            'cloud_return': str(cloud_return_path.relative_to(RAGSTACK_ROOT)) if cloud_return_path.is_file() else None,
        },
    }


def brain_exchange_summaries(limit: int = 50) -> dict[str, Any]:
    if not CHAT_LOG_DIR.exists():
        return {'count': 0, 'exchanges': []}
    paths = sorted(CHAT_LOG_DIR.glob('*.json'), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]
    exchanges = [brain_exchange_summary(path) for path in paths]
    return {'count': len(exchanges), 'exchanges': exchanges}


def privacy_prompt_summaries() -> list[dict[str, Any]]:
    if not PRIVACY_CHOICES.exists():
        return []
    data = load_json_file(PRIVACY_CHOICES)
    prompts: list[dict[str, Any]] = []
    choices = data.get('choices', data)
    if isinstance(choices, dict):
        for key, value in sorted(choices.items()):
            if isinstance(value, dict):
                prompts.append({
                    'id': str(key),
                    'privacy_class': str(value.get('privacy_class', '')),
                    'reason': str(value.get('reason', '')),
                })
            else:
                prompts.append({'id': str(key), 'privacy_class': str(value), 'reason': ''})
    return prompts


def safe_route_message(route: str) -> str:
    messages = {
        'memory_direct': 'FrontGate routed this as a local memory request.',
        'blocked': 'FrontGate blocked this request.',
        'needs_user_privacy_question': 'FrontGate needs a privacy answer before continuing.',
        'needs_human_approval': 'FrontGate routed this request to human approval.',
        'worker_pi_agent': 'FrontGate routed this to a local worker path.',
    }
    return messages.get(route, 'FrontGate returned a route.')


def load_citadel_contract():
    module_path = RAGSTACK_ROOT / 'gateway' / 'citadel' / 'main.py'
    spec = importlib.util.spec_from_file_location('ragstackproxy_citadel_bridge_contract', module_path)
    if spec is None or spec.loader is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Citadel contract is unavailable')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def handoff_error_payload(exc: HTTPException) -> dict[str, Any]:
    detail = exc.detail if isinstance(exc.detail, dict) else {'error': str(exc.detail)}
    provider_error: Any = detail.get('upstream_body') or detail.get('provider_error') or detail
    if isinstance(provider_error, str):
        try:
            provider_error = json.loads(provider_error)
        except Exception:
            pass
    if isinstance(provider_error, dict) and isinstance(provider_error.get('detail'), dict):
        provider_error = provider_error['detail'].get('provider_error', provider_error['detail'])
    if isinstance(provider_error, dict) and isinstance(provider_error.get('provider_error'), dict):
        provider_error = provider_error['provider_error']
    error_obj = provider_error.get('error', {}) if isinstance(provider_error, dict) else {}
    error_code = ''
    if isinstance(error_obj, dict):
        error_code = str(error_obj.get('code') or error_obj.get('type') or '')
    suffix = f' Provider error: {error_code}.' if error_code else ''
    return {
        'answer': 'RagStackProxy routed this through OutboundGate, but the configured external provider did not return an answer. Check the outbound provider configuration or use the public_web provider.' + suffix,
        'redactions': ['handoff_error'],
        'metadata': {
            'external_called': False,
            'handoff_error': detail,
        },
    }


@router.get('/status')
async def get_ragstackproxy_status(_: None = Depends(require_ragstackproxy_token)):
    approvals = approval_summaries()
    handoffs = handoff_summaries(limit=10)
    return {
        'status': 'RagStackProxy Citadel bridge running',
        'created': utc_now(),
        'install_root': str(RAGSTACK_ROOT),
        'frontgate_url': FRONTGATE_URL,
        'outboundgate_url': OUTBOUNDGATE_URL,
        'approval_counts': approvals['counts'],
        'handoff_counts': handoffs['counts'],
        'privacy_prompt_count': len(privacy_prompt_summaries()),
    }


@router.post('/chat')
async def post_ragstackproxy_chat(payload: ChatRequest, _: None = Depends(require_ragstackproxy_token)):
    contract = load_citadel_contract()
    if hasattr(contract, 'process_chat_message'):
        result = await asyncio.to_thread(
            contract.process_chat_message,
            payload.message,
            user_id=payload.user,
            selected_model='LocalBrain',
        )
        route = result.get('debug_drawer', {}).get('route', {})
        return {
            'created': utc_now(),
            'route': route,
            'approval_status': result.get('debug_drawer', {}).get('approval', {}).get('state', 'not_required'),
            'handoff_status': 'completed' if result.get('artifacts', {}).get('handoff_record') else 'not_started',
            'safe_answer': result.get('user_visible_answer', ''),
            'debug': result.get('debug_drawer', {}),
            'artifacts': result.get('artifacts', {}),
        }

    selected_model, rejected_model = contract.resolve_chat_model('LocalBrain')
    route = contract.route_request(payload.message)
    response: dict[str, Any] = {
        'created': utc_now(),
        'route': route,
        'approval_status': 'not_required',
        'handoff_status': 'not_started',
        'safe_answer': contract.natural_answer(payload.message, route),
        'debug': contract.safe_debug_state(route, selected_model=selected_model, rejected_model=rejected_model),
    }
    if route.get('route') == 'approval_required':
        response['approval_status'] = 'pending'
    if route.get('route') == 'privacy_question':
        response['privacy_prompt'] = 'Please choose whether this information may be summarized outside the box.'
    if route.get('route') == 'cloudbrain_via_outboundgate':
        handoff_payload = {
            **route,
            'payload': payload.message,
            'memory_ids': payload.memory_ids,
            'request_id': f'citadel-{secrets.token_hex(8)}',
            'session_id': payload.session_id,
            'user': payload.user,
            'company_id': payload.company_id,
            'role': payload.role,
            'provider': payload.provider,
        }
        try:
            handoff = await post_json(OUTBOUNDGATE_URL, handoff_payload)
        except HTTPException as exc:
            handoff = handoff_error_payload(exc)
        metadata = handoff.get('metadata', {}) if isinstance(handoff.get('metadata'), dict) else {}
        response.update({
            'handoff_status': 'completed' if metadata.get('external_called') else 'not_called',
            'safe_answer': str(handoff.get('answer', '')),
            'handoff': {
                'redactions': handoff.get('redactions', []),
                'metadata': {
                    key: value
                    for key, value in metadata.items()
                    if key
                    in {
                        'external_called',
                        'provider',
                        'provider_type',
                        'request_id',
                        'sent_payload_hash',
                        'returned_payload_hash',
                        'return_scan',
                        'memory_ids_sent',
                        'sent_record',
                        'returned_record',
                        'raw_inbox_record',
                        'handoff_error',
                    }
                },
            },
        })
    return response


@router.get('/memories')
async def get_ragstackproxy_memories(_: None = Depends(require_ragstackproxy_token)):
    summaries = memory_summaries()
    return {'count': len(summaries), 'memories': summaries}


@router.get('/approvals')
async def get_ragstackproxy_approvals(_: None = Depends(require_ragstackproxy_token)):
    return approval_summaries()


@router.get('/handoffs')
async def get_ragstackproxy_handoffs(_: None = Depends(require_ragstackproxy_token)):
    return handoff_summaries()


@router.get('/brain-exchanges')
async def get_ragstackproxy_brain_exchanges(
    limit: int = 50,
    _: None = Depends(require_ragstackproxy_token),
):
    return brain_exchange_summaries(limit=max(1, min(limit, 200)))


@router.get('/privacy-prompts')
async def get_ragstackproxy_privacy_prompts(_: None = Depends(require_ragstackproxy_token)):
    prompts = privacy_prompt_summaries()
    return {'count': len(prompts), 'prompts': prompts}

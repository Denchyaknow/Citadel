from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from open_webui.internal.db import get_async_session
from open_webui.models.chat_messages import ChatMessage, _token_columns
from open_webui.models.chats import Chat
from open_webui.utils.auth import get_verified_user
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def _safe_int(value: Any) -> int:
    try:
        return max(int(float(value or 0)), 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        if isinstance(value, str):
            value = value.strip().replace('$', '').replace(',', '')
            if not value:
                return 0.0
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _usage_cost(usage: Any) -> float:
    if not isinstance(usage, dict):
        return 0.0
    for key in ('estimated_cost', 'estimated_cost_usd', 'cost', 'total_cost'):
        cost = _safe_float(usage.get(key))
        if cost:
            return cost
    return 0.0


def _format_bytes(value: int | float) -> str:
    size = float(value or 0)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024 or unit == 'TB':
            return f'{size:.1f} {unit}' if unit != 'B' else f'{int(size)} B'
        size /= 1024
    return f'{size:.1f} TB'


def _cpu_percent() -> float | None:
    try:
        first = _read_proc_stat_cpu()
        time.sleep(0.08)
        second = _read_proc_stat_cpu()
        idle_delta = second['idle'] - first['idle']
        total_delta = second['total'] - first['total']
        if total_delta <= 0:
            return None
        return round(max(0.0, min(100.0, (1 - (idle_delta / total_delta)) * 100)), 1)
    except Exception:
        return None


def _read_proc_stat_cpu() -> dict[str, int]:
    parts = Path('/proc/stat').read_text(encoding='utf-8').splitlines()[0].split()[1:]
    values = [int(part) for part in parts]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return {'idle': idle, 'total': sum(values)}


def _memory_usage() -> dict[str, Any]:
    values: dict[str, int] = {}
    try:
        for line in Path('/proc/meminfo').read_text(encoding='utf-8').splitlines():
            key, raw = line.split(':', 1)
            values[key] = int(raw.strip().split()[0]) * 1024
    except Exception:
        values = {}

    total = values.get('MemTotal', 0)
    available = values.get('MemAvailable', 0)
    used = max(total - available, 0)
    percent = round((used / total) * 100, 1) if total else 0.0
    return {
        'used': used,
        'total': total,
        'available': available,
        'percent': percent,
        'label': f'{_format_bytes(used)} / {_format_bytes(total)}',
    }


def _disk_usage() -> dict[str, Any]:
    usage = shutil.disk_usage('/')
    percent = round((usage.used / usage.total) * 100, 1) if usage.total else 0.0
    return {
        'used': usage.used,
        'total': usage.total,
        'available': usage.free,
        'percent': percent,
        'label': f'{_format_bytes(usage.used)} / {_format_bytes(usage.total)}',
    }


def _system_health() -> dict[str, Any]:
    cpu = _cpu_percent()
    return {
        'status': 'ok',
        'checked_at': int(time.time()),
        'cpu': {
            'percent': cpu if cpu is not None else 0.0,
            'label': f'{cpu:.1f}%' if cpu is not None else 'Unavailable',
        },
        'memory': _memory_usage(),
        'disk': _disk_usage(),
    }


def _skill_usage_paths() -> list[Path]:
    candidates: list[Path] = []
    env_home = os.environ.get('HERMES_HOME')
    homes = [Path(env_home).expanduser()] if env_home else []
    homes.append(Path.home() / '.hermes')

    for home in homes:
        candidates.append(home / 'skills' / '.usage.json')
        profiles_dir = home / 'profiles'
        try:
            candidates.extend(sorted(profiles_dir.glob('*/skills/.usage.json')))
        except Exception:
            pass

    seen: set[Path] = set()
    result: list[Path] = []
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def _skill_usage() -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    sources: list[str] = []

    for path in _skill_usage_paths():
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        sources.append(str(path))
        for name, meta in raw.items():
            if not isinstance(meta, dict):
                continue
            bucket = merged.setdefault(str(name), {'use_count': 0, 'view_count': 0, 'patch_count': 0})
            bucket['use_count'] += _safe_int(meta.get('use_count'))
            bucket['view_count'] += _safe_int(meta.get('view_count'))
            bucket['patch_count'] += _safe_int(meta.get('patch_count'))

    total_invocations = sum(item['use_count'] for item in merged.values())
    return {
        'usage': dict(sorted(merged.items(), key=lambda item: (-item[1]['use_count'], item[0]))),
        'skill_names': sorted(merged.keys()),
        'total_invocations': total_invocations,
        'unique_skills_used': sum(1 for item in merged.values() if item['use_count'] > 0),
        'sources': sources,
    }


@router.get('/summary')
async def get_status_summary(
    days: int = Query(30, ge=1, le=365),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    now = int(time.time())
    today = time.localtime(now)
    today_midnight = int(
        time.mktime((today.tm_year, today.tm_mon, today.tm_mday, 0, 0, 0, today.tm_wday, today.tm_yday, today.tm_isdst))
    )
    first_day_ts = today_midnight - ((days - 1) * 86400)
    user_filter = [] if user.role == 'admin' else [Chat.user_id == user.id]
    message_user_filter = [] if user.role == 'admin' else [ChatMessage.user_id == user.id]

    sessions_stmt = select(func.count(Chat.id)).where(
        or_(Chat.created_at >= first_day_ts, Chat.updated_at >= first_day_ts),
        *user_filter,
    )
    total_sessions = _safe_int((await db.execute(sessions_stmt)).scalar())

    chats_stmt = select(Chat.created_at, Chat.updated_at).where(
        or_(Chat.created_at >= first_day_ts, Chat.updated_at >= first_day_ts),
        *user_filter,
    )
    chat_rows = (await db.execute(chats_stmt)).all()

    bind = await db.connection()
    dialect = bind.dialect.name
    input_tokens_col, output_tokens_col = _token_columns(dialect)
    messages_stmt = (
        select(
            ChatMessage.created_at,
            ChatMessage.role,
            ChatMessage.model_id,
            ChatMessage.usage,
            func.coalesce(input_tokens_col, 0).label('input_tokens'),
            func.coalesce(output_tokens_col, 0).label('output_tokens'),
        )
        .where(ChatMessage.created_at >= first_day_ts, *message_user_filter)
        .order_by(ChatMessage.created_at.asc())
    )
    message_rows = (await db.execute(messages_stmt)).all()

    total_messages = len(message_rows)
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    model_stats: dict[str, dict[str, Any]] = {}
    daily_tokens: dict[str, dict[str, Any]] = {}

    for row in message_rows:
        input_tokens = _safe_int(row.input_tokens)
        output_tokens = _safe_int(row.output_tokens)
        cost = _usage_cost(row.usage)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        total_cost += cost

        day_key = time.strftime('%Y-%m-%d', time.localtime(_safe_int(row.created_at)))
        daily = daily_tokens.setdefault(
            day_key,
            {'input_tokens': 0, 'output_tokens': 0, 'sessions': 0, 'cost': 0.0},
        )
        daily['input_tokens'] += input_tokens
        daily['output_tokens'] += output_tokens
        daily['cost'] += cost

        if row.role == 'assistant' and row.model_id:
            model = str(row.model_id)
            bucket = model_stats.setdefault(
                model,
                {'sessions': set(), 'messages': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost': 0.0},
            )
            bucket['messages'] += 1
            bucket['input_tokens'] += input_tokens
            bucket['output_tokens'] += output_tokens
            bucket['cost'] += cost

    for chat_created, chat_updated in chat_rows:
        ts = max(_safe_int(chat_created), _safe_int(chat_updated))
        day_key = time.strftime('%Y-%m-%d', time.localtime(ts))
        daily = daily_tokens.setdefault(
            day_key,
            {'input_tokens': 0, 'output_tokens': 0, 'sessions': 0, 'cost': 0.0},
        )
        daily['sessions'] += 1

    total_tokens = total_input_tokens + total_output_tokens
    models = []
    for model, stats in model_stats.items():
        model_tokens = stats['input_tokens'] + stats['output_tokens']
        models.append(
            {
                'model': model,
                'messages': stats['messages'],
                'input_tokens': stats['input_tokens'],
                'output_tokens': stats['output_tokens'],
                'total_tokens': model_tokens,
                'cost': round(stats['cost'], 6),
                'token_share': int(round((model_tokens / total_tokens) * 100)) if total_tokens else 0,
                'cost_share': int(round((stats['cost'] / total_cost) * 100)) if total_cost else 0,
            }
        )
    models.sort(key=lambda row: (-row['total_tokens'], -row['messages'], row['model']))

    daily_series = []
    for index in range(days):
        day_ts = first_day_ts + (index * 86400)
        day_key = time.strftime('%Y-%m-%d', time.localtime(day_ts))
        bucket = daily_tokens.get(day_key, {'input_tokens': 0, 'output_tokens': 0, 'sessions': 0, 'cost': 0.0})
        daily_series.append(
            {
                'date': day_key,
                'input_tokens': bucket['input_tokens'],
                'output_tokens': bucket['output_tokens'],
                'sessions': bucket['sessions'],
                'cost': round(bucket['cost'], 6),
            }
        )

    day_counts = {i: 0 for i in range(7)}
    hour_counts = {i: 0 for i in range(24)}
    for chat_created, chat_updated in chat_rows:
        ts = max(_safe_int(chat_created), _safe_int(chat_updated))
        if not ts:
            continue
        dt = time.localtime(ts)
        day_counts[dt.tm_wday] += 1
        hour_counts[dt.tm_hour] += 1

    day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    return {
        'period_days': days,
        'scope': 'global' if user.role == 'admin' else 'user',
        'system_health': _system_health(),
        'skill_usage': _skill_usage(),
        'total_sessions': total_sessions,
        'total_messages': total_messages,
        'total_input_tokens': total_input_tokens,
        'total_output_tokens': total_output_tokens,
        'total_tokens': total_tokens,
        'total_cost': round(total_cost, 6),
        'models': models,
        'daily_tokens': daily_series,
        'activity_by_day': [{'day': day_labels[index], 'sessions': day_counts[index]} for index in range(7)],
        'activity_by_hour': [{'hour': index, 'sessions': hour_counts[index]} for index in range(24)],
    }

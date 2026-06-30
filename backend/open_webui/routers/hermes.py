from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.utils.access_control import has_permission
from open_webui.utils.auth import get_verified_user
from open_webui.utils.hermes import (
    create_hermes_cron_job,
    delete_hermes_cron_job,
    hermes_cron_job,
    hermes_cron_job_runs,
    hermes_cron_jobs,
    hermes_health,
    hermes_profiles,
    hermes_sessions,
    hermes_skills,
    pause_hermes_cron_job,
    resume_hermes_cron_job,
    sync_hermes_sessions_to_chats,
    trigger_hermes_cron_job,
    update_hermes_cron_job,
)

router = APIRouter()


class HermesCronJobCreate(BaseModel):
    prompt: str = ''
    schedule: str
    name: str = ''
    deliver: str = 'local'
    skills: list[str] | None = None
    model: str | None = None
    provider: str | None = None
    base_url: str | None = None
    script: str | None = None
    context_from: Any | None = None
    enabled_toolsets: list[str] | None = None
    workdir: str | None = None
    no_agent: bool = False


class HermesCronJobUpdate(BaseModel):
    updates: dict[str, Any]


async def require_automation_access(request: Request, user) -> None:
    if not getattr(request.app.state.config, 'ENABLE_AUTOMATIONS', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )
    if user.role == 'admin':
        return
    if await has_permission(user.id, 'features.automations', request.app.state.config.USER_PERMISSIONS):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.UNAUTHORIZED,
    )


@router.get('/status')
async def get_hermes_status(user=Depends(get_verified_user)):
    return await hermes_health()


@router.get('/profiles')
async def get_hermes_profiles(user=Depends(get_verified_user)):
    return await hermes_profiles()


@router.get('/sessions')
async def get_hermes_sessions(user=Depends(get_verified_user)):
    return await hermes_sessions()


@router.post('/sync')
async def sync_hermes_sessions(user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    synced = await sync_hermes_sessions_to_chats(user, db=db)
    return {'ok': True, 'synced': synced}


@router.get('/skills')
async def get_hermes_skills(user=Depends(get_verified_user)):
    return await hermes_skills()


@router.get('/cron/jobs')
async def list_hermes_cron_jobs(
    request: Request,
    profile: str = Query('all'),
    user=Depends(get_verified_user),
):
    await require_automation_access(request, user)
    return await hermes_cron_jobs(profile)


@router.get('/cron/jobs/{job_id}')
async def get_hermes_cron_job(
    request: Request,
    job_id: str,
    profile: str | None = Query(None),
    user=Depends(get_verified_user),
):
    await require_automation_access(request, user)
    return await hermes_cron_job(job_id, profile)


@router.get('/cron/jobs/{job_id}/runs')
async def get_hermes_cron_job_runs(
    request: Request,
    job_id: str,
    profile: str | None = Query(None),
    limit: int = Query(20),
    user=Depends(get_verified_user),
):
    await require_automation_access(request, user)
    return await hermes_cron_job_runs(job_id, profile, limit)


@router.post('/cron/jobs')
async def create_hermes_cron_job_route(
    request: Request,
    form_data: HermesCronJobCreate,
    profile: str = Query('default'),
    user=Depends(get_verified_user),
):
    await require_automation_access(request, user)
    return await create_hermes_cron_job(profile, form_data.model_dump(exclude_none=True), user)


@router.put('/cron/jobs/{job_id}')
async def update_hermes_cron_job_route(
    request: Request,
    job_id: str,
    form_data: HermesCronJobUpdate,
    profile: str | None = Query(None),
    user=Depends(get_verified_user),
):
    await require_automation_access(request, user)
    return await update_hermes_cron_job(profile, job_id, form_data.updates)


@router.post('/cron/jobs/{job_id}/pause')
async def pause_hermes_cron_job_route(
    request: Request,
    job_id: str,
    profile: str | None = Query(None),
    user=Depends(get_verified_user),
):
    await require_automation_access(request, user)
    return await pause_hermes_cron_job(profile, job_id)


@router.post('/cron/jobs/{job_id}/resume')
async def resume_hermes_cron_job_route(
    request: Request,
    job_id: str,
    profile: str | None = Query(None),
    user=Depends(get_verified_user),
):
    await require_automation_access(request, user)
    return await resume_hermes_cron_job(profile, job_id)


@router.post('/cron/jobs/{job_id}/trigger')
async def trigger_hermes_cron_job_route(
    request: Request,
    job_id: str,
    profile: str | None = Query(None),
    user=Depends(get_verified_user),
):
    await require_automation_access(request, user)
    return await trigger_hermes_cron_job(profile, job_id)


@router.delete('/cron/jobs/{job_id}')
async def delete_hermes_cron_job_route(
    request: Request,
    job_id: str,
    profile: str | None = Query(None),
    user=Depends(get_verified_user),
):
    await require_automation_access(request, user)
    return await delete_hermes_cron_job(profile, job_id)

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from open_webui.internal.db import get_async_session
from open_webui.utils.auth import get_verified_user
from open_webui.utils.hermes import (
    hermes_health,
    hermes_profiles,
    hermes_sessions,
    hermes_skills,
    sync_hermes_sessions_to_chats,
)

router = APIRouter()


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

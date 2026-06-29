from __future__ import annotations

from fastapi import APIRouter, Depends
from open_webui.utils.auth import get_verified_user
from open_webui.utils.hermes import hermes_health, hermes_profiles, hermes_sessions, hermes_skills

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


@router.get('/skills')
async def get_hermes_skills(user=Depends(get_verified_user)):
    return await hermes_skills()

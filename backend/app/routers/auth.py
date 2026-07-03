from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from app.services.auth_db import auth_db

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(body: LoginRequest):
    if not auth_db.verify_user(body.username, body.password):
        logger.warning("[auth] login failed for username=%s", body.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = auth_db.create_session(body.username)
    user = auth_db.get_user(body.username)
    return {"token": token, "username": body.username, "role": user.role if user else "user"}


@router.post("/auth/register")
async def register(body: RegisterRequest):
    if auth_db.user_exists(body.username):
        logger.warning("[auth] register failed, user exists: username=%s", body.username)
        raise HTTPException(status_code=409, detail="User already exists")
    if len(body.username.strip()) < 2:
        logger.warning("[auth] register failed, short username: username=%s", body.username)
        raise HTTPException(status_code=400, detail="Username is too short")
    if len(body.password) < 4:
        logger.warning("[auth] register failed, short password: username=%s", body.username)
        raise HTTPException(status_code=400, detail="Password is too short")

    try:
        auth_db.create_user(body.username.strip(), body.password, role="user")
    except ValueError as exc:
        logger.warning("[auth] register failed for username=%s: %s", body.username, str(exc))
        raise HTTPException(status_code=409, detail="User already exists") from exc

    return {"ok": True}


@router.get("/auth/me")
async def me(token: str):
    username = auth_db.get_username_by_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = auth_db.get_user(username)
    return {"username": username, "role": user.role if user else "user"}


@router.post("/auth/logout")
async def logout(token: str):
    auth_db.delete_session(token)
    return {"ok": True}


@router.post("/auth/ssh-key")
async def upload_ssh_key(payload: dict):
    """Upload a public SSH key to the server. Requires a valid session token."""
    token = payload.get('token', '')
    username = auth_db.get_username_by_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pubkey = (payload.get('pubkey', '') or '').strip()
    if not pubkey or not pubkey.startswith('ssh-'):
        raise HTTPException(status_code=400, detail="Invalid public key")

    import os
    ssh_dir = os.path.expanduser('~/.ssh')
    os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
    auth_keys_path = os.path.join(ssh_dir, 'authorized_keys')

    # Check if key already exists
    existing = ''
    if os.path.exists(auth_keys_path):
        existing = open(auth_keys_path, 'r').read()
    if pubkey in existing:
        return {"ok": True, "message": "Key already exists"}

    with open(auth_keys_path, 'a') as f:
        f.write(f'\n{pubkey} # {username} via VGuard\n')
    os.chmod(auth_keys_path, 0o600)
    return {"ok": True, "message": "SSH key uploaded successfully"}

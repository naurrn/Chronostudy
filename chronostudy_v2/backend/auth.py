import secrets
from fastapi import Header, HTTPException, Depends
import database as db


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def get_current_user(authorization: str = Header(default=None)):
    """
    Expects header: Authorization: Bearer <token>
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Tidak terautentikasi.")

    token = authorization.removeprefix("Bearer ").strip()
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Sesi tidak valid atau sudah berakhir.")

    return user

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_token, current_user, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas import AuthOut, LoginIn, RegisterIn, SettingsIn, UserOut
import datetime as dt

from .. import ratelimit

# Hash checked when the email doesn't exist, so response time doesn't reveal which emails have accounts
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check(f"register:{ratelimit.client_ip(request)}", 5, 3600, "Too many new accounts from this network.")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "An account with that email already exists. Sign in instead.")
    user = User(email=body.email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return {"token": create_token(user.id), "user": user}


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    ratelimit.check(f"login-ip:{ratelimit.client_ip(request)}", 20, 900, "Too many sign-in attempts.")
    ratelimit.check(f"login-email:{email}", 5, 900, "Too many sign-in attempts for this account.")
    user = db.scalar(select(User).where(User.email == email))
    password_ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not password_ok:
        raise HTTPException(401, "That email and password don't match.")
    return {"token": create_token(user.id), "user": user}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.put("/settings", response_model=UserOut)
def update_settings(body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.current_balance = body.current_balance
    user.balance_as_of = dt.date.today()
    user.low_balance_threshold = body.low_balance_threshold
    if body.name is not None:
        user.name = body.name.strip()
    db.add(user)
    db.commit()
    return user

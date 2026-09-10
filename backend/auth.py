"""JWT + password auth. Register / login / me endpoints."""
import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr, Field
from db import db, new_id, now_iso, strip_mongo

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_EXP_DAYS = 30

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- helpers ---
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def make_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXP_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(401, "User not found")
    return strip_mongo(user)


async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


def require_role(*roles):
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(403, "Not authorized")
        return user
    return _check


# --- models ---
class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    role: str = "buyer"  # buyer | artist


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    role: str
    bio: Optional[str] = None
    cover_image: Optional[str] = None
    avatar: Optional[str] = None
    approved: bool = True


def public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u["name"],
        "role": u["role"],
        "bio": u.get("bio"),
        "cover_image": u.get("cover_image"),
        "avatar": u.get("avatar"),
        "onboarded": bool(u.get("onboarded")),
        "approved": u.get("approved", True),
    }


# --- endpoints ---
@router.post("/register")
async def register(req: RegisterReq):
    if req.role not in ("buyer", "artist"):
        raise HTTPException(400, "Invalid role")
    existing = await db.users.find_one({"email": req.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")
    user = {
        "id": new_id(),
        "email": req.email.lower(),
        "password_hash": hash_password(req.password),
        "name": req.name,
        "role": req.role,
        "bio": None,
        "cover_image": None,
        "avatar": None,
        "approved": True,  # auto-approve for v1
        "stripe_connect_status": "not_started",
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    await db.event_rsvps.update_many({"gift_email": user["email"], "user_id": None}, {"$set": {"user_id": user["id"]}})
    token = make_token(user["id"], user["role"])
    return {"token": token, "user": public_user(user)}


@router.post("/login")
async def login(req: LoginReq):
    user = await db.users.find_one({"email": req.email.lower()})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = make_token(user["id"], user["role"])
    return {"token": token, "user": public_user(user)}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


class UpdateProfileReq(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    cover_image: Optional[str] = None
    avatar: Optional[str] = None


@router.patch("/me")
async def update_me(req: UpdateProfileReq, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in req.model_dump(exclude_none=True).items()}
    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
    fresh = strip_mongo(await db.users.find_one({"id": user["id"]}))
    return public_user(fresh)

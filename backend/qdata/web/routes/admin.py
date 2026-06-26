from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from qdata.auth.dependencies import get_current_user
from qdata.auth.jwt import create_access_token, hash_password
from qdata.auth.permissions import require_permission
from qdata.db.models import User
from qdata.db.session import get_session

router = APIRouter()


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: str | None = None

    model_config = {"from_attributes": True}


class UpdateRoleRequest(BaseModel):
    role: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""
    role: str = "analyst"


@router.get("/users")
async def list_users(
    user: User = Depends(require_permission("manage:users")),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        UserOut(
            id=str(u.id),
            email=u.email,
            name=u.name or "",
            role=u.role or "analyst",
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in users
    ]


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    req: UpdateRoleRequest,
    user: User = Depends(require_permission("manage:users")),
    session: AsyncSession = Depends(get_session),
):
    if req.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be: admin, analyst, viewer")

    result = await session.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.role = req.role
    await session.commit()
    return {"status": "ok"}


@router.post("/users", status_code=201)
async def create_user(
    req: CreateUserRequest,
    user: User = Depends(require_permission("manage:users")),
    session: AsyncSession = Depends(get_session),
):
    if req.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be: admin, analyst, viewer")

    result = await session.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name or req.email.split("@")[0],
        role=req.role,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return UserOut(
        id=str(new_user.id),
        email=new_user.email,
        name=new_user.name or "",
        role=new_user.role or "analyst",
        created_at=new_user.created_at.isoformat() if new_user.created_at else None,
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user: User = Depends(require_permission("manage:users")),
    session: AsyncSession = Depends(get_session),
):
    if str(user.id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await session.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(target)
    await session.commit()
    return {"status": "ok"}

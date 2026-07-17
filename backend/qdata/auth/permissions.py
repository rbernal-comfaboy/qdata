from fastapi import Depends, HTTPException, status

from qdata.auth.dependencies import get_current_user
from qdata.db.models import User

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"create:source", "create:analysis", "view:report", "view:any:report", "manage:users"},
    "analyst": {"create:source", "create:analysis", "view:report"},
    "viewer": {"view:report"},
}

MUTABLE_ROLES = ("admin",)


def require_permission(permission: str):
    async def check(user: User = Depends(get_current_user)) -> User:
        perms = ROLE_PERMISSIONS.get(user.role, set())
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return user
    return check


def require_role(allowed_roles: list[str]):
    async def check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acción no permitida para este rol",
            )
        return user
    return check

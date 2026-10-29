from typing import Optional, List
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole
from app.core.security import decode_access_token
from app.core.exceptions import UnauthenticatedException, ForbiddenException

bearer_scheme = HTTPBearer(auto_error=False)


def get_token_from_header(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    """Extract raw bearer token or raise UnauthenticatedException."""
    if not auth or not auth.credentials:
        raise UnauthenticatedException("Authorization bearer token is missing or malformed.")
    return auth.credentials


def get_current_user(
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db),
) -> User:
    """Validate bearer token and resolve authenticated user from database."""
    payload = decode_access_token(token)
    if not payload:
        raise UnauthenticatedException("Invalid, expired, or revoked authentication token.")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthenticatedException("Malformed authentication token claims.")

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise UnauthenticatedException("Invalid user identifier in token claims.")

    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise UnauthenticatedException("User account does not exist.")

    if not user.is_active:
        raise ForbiddenException("User account has been deactivated.")

    # Attach session metadata for fine-grained authorization and synthetic demo boundaries
    user.is_demo_session = bool(payload.get("is_demo", False))
    user.token_scope = str(payload.get("scope", "synthetic_demo" if user.is_demo_session else "standard"))
    user.demo_persona = payload.get("demo_persona")

    return user


def require_roles(allowed_roles: List[UserRole]):
    """Role-based access control dependency factory."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                f"Access denied: Required role '{[r.value for r in allowed_roles]}' not held by current user."
            )
        return current_user

    return role_checker

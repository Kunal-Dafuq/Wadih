from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import verify_password, create_access_token, blacklist_token
from app.core.exceptions import UnauthenticatedException
from app.schemas.auth import TokenResponse, CurrentUserResponse


class AuthService:
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        """Verify user credentials and return active user, or raise UnauthenticatedException."""
        user = db.query(User).filter(User.email == email.lower().strip()).first()
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthenticatedException("Invalid email or password.")

        if not user.is_active:
            raise UnauthenticatedException("Account is deactivated.")

        return user

    @staticmethod
    def create_token_for_user(user: User) -> TokenResponse:
        """Generate JWT access token and user info payload."""
        token_payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        }
        token = create_access_token(token_payload)

        display_name = user.profile.display_name if user.profile else user.email.split("@")[0]
        pref_lang = user.profile.preferred_language if user.profile else "en"
        lit_mode = user.profile.literacy_mode if user.profile else "standard"

        user_resp = CurrentUserResponse(
            id=user.id,
            email=user.email,
            role=token_payload["role"],
            is_active=user.is_active,
            display_name=display_name,
            preferred_language=pref_lang,
            literacy_mode=lit_mode,
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=user_resp,
        )

    @staticmethod
    def logout_token(token: str) -> None:
        """Invalidate the session token server-side."""
        blacklist_token(token)

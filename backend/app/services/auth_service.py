from datetime import timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.core.security import verify_password, create_access_token, blacklist_token
from app.core.exceptions import UnauthenticatedException, ValidationException, ForbiddenException
from app.schemas.auth import TokenResponse, CurrentUserResponse


class AuthService:
    DEMO_PERSONAS = {
        "patient_a": "patient.a@wadih.demo",
        "patient_b": "patient.b@wadih.demo",
        "counsellor": "counsellor@wadih.demo",
    }

    @classmethod
    def authenticate_demo_persona(cls, db: Session, persona: str) -> User:
        """Safely authenticate a synthetic demonstration persona without requiring exposed passwords."""
        clean_key = (persona or "").lower().strip()
        email = cls.DEMO_PERSONAS.get(clean_key)
        if not email:
            raise ValidationException(
                "Invalid demo persona. Supported synthetic demonstration personas: 'patient_a', 'patient_b', 'counsellor'."
            )
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise UnauthenticatedException(f"Demo account for persona '{clean_key}' not found.")
        if not user.is_active:
            raise UnauthenticatedException("Demo persona account is deactivated.")
        if user.role == UserRole.ADMIN:
            raise ForbiddenException("Administrator accounts are not permitted for demonstration sessions.")
        return user

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
    def create_token_for_user(
        user: User,
        is_demo: bool = False,
        demo_persona: Optional[str] = None,
    ) -> TokenResponse:
        """Generate JWT access token and user info payload.

        Demo sessions receive:
        - 30-minute reduced token expiration.
        - Explicit is_demo=True and scope='synthetic_demo' claims.
        """
        scope = "synthetic_demo" if is_demo else "standard"
        token_payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "is_demo": is_demo,
            "scope": scope,
            "demo_persona": demo_persona if is_demo else None,
        }
        expires_delta = timedelta(minutes=30) if is_demo else None
        token = create_access_token(token_payload, expires_delta=expires_delta)

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
            is_demo_session=is_demo,
            token_scope=scope,
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            is_demo=is_demo,
            scope=scope,
            user=user_resp,
        )

    @staticmethod
    def logout_token(token: str) -> None:
        """Invalidate the session token server-side."""
        blacklist_token(token)

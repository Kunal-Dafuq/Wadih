from sqlalchemy.orm import Session
from app.models.user import User
from app.models.participant import ParticipantProfile
from app.schemas.user import ParticipantProfileUpdateRequest
from app.core.exceptions import NotFoundException


class UserService:
    @staticmethod
    def get_or_create_profile(db: Session, user: User) -> ParticipantProfile:
        """Retrieve existing profile or initialize a default profile for the user."""
        profile = db.query(ParticipantProfile).filter(ParticipantProfile.user_id == user.id).first()
        if not profile:
            profile = ParticipantProfile(
                user_id=user.id,
                display_name=user.email.split("@")[0],
                preferred_language="en",
                literacy_mode="standard",
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return profile

    @staticmethod
    def update_profile(
        db: Session, user: User, update_data: ParticipantProfileUpdateRequest
    ) -> ParticipantProfile:
        """Update permitted preferences on the authenticated user's own profile."""
        profile = UserService.get_or_create_profile(db, user)

        if update_data.display_name is not None:
            profile.display_name = update_data.display_name.strip()
        if update_data.preferred_language is not None:
            profile.preferred_language = update_data.preferred_language.lower().strip()
        if update_data.literacy_mode is not None:
            profile.literacy_mode = update_data.literacy_mode.strip()

        db.commit()
        db.refresh(profile)
        return profile

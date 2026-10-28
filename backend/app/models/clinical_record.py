from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class ClinicalResidualRiskRecord(Base):
    """Authoritative, clinician-reviewed residual-risk assessment record.

    Provides server-controlled clinical provenance for carrier screening negative results.
    Binds the residual carrier probability to:
    - Target screening case (identifying the negative partner)
    - Condition code (e.g. HBB_BETA_THAL)
    - Validated numerical probability (0.0 < r < 1.0)
    - Authoritative clinical laboratory source reference (e.g. ACMG-compliant detection rate documentation)
    - Reviewing clinician / medical geneticist ID
    - Verification timestamp and active status
    """
    __tablename__ = "clinical_residual_risk_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(
        Integer,
        ForeignKey("screening_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    condition_code = Column(String(64), index=True, nullable=False)
    residual_carrier_probability = Column(Float, nullable=False)
    clinical_source_reference = Column(String(255), nullable=False)
    reviewing_clinician_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    reviewed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    case = relationship("ScreeningCase", backref="clinical_residual_risk_records")
    reviewing_clinician = relationship("User", foreign_keys=[reviewing_clinician_id])

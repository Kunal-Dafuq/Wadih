"""Shared entity definitions.

Maintained for backward compatibility with foundational backend imports.
Full models are implemented in app.models.consent and app.models.audit.
"""

from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
from app.models.audit import AuditLog

# Aliases for initial stub references
SharedConsentGrantStub = ConsentGrant
SharedAuditLogStub = AuditLog

__all__ = [
    "ConsentGrant",
    "ConsentStatus",
    "ConsentScope",
    "AuditLog",
    "SharedConsentGrantStub",
    "SharedAuditLogStub",
]

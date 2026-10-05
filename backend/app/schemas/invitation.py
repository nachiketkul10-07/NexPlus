"""Request and response models for administrator-issued registration invitations."""
from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegistrationInvitationCreate(BaseModel):
    email: EmailStr


class RegistrationInvitationResponse(BaseModel):
    email: EmailStr
    invitation_code: str
    expires_at: datetime

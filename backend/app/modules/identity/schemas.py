import uuid

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """The form a person fills in to log in."""

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """The answer we send back: the wristband."""

    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """After the password: the wristband, or (admins and billing) the second-factor step.

    Everyone else gets access_token straight away, as before. Admins and billing get no
    token yet: mfa says which step ("setup" the first time, then "verify") and
    challenge_token carries them to it for 5 minutes.
    """

    access_token: str | None = None
    token_type: str = "bearer"
    mfa: str | None = None
    challenge_token: str | None = None


class MfaChallenge(BaseModel):
    challenge_token: str = Field(min_length=1, max_length=2000)


class MfaCode(MfaChallenge):
    """A 6-digit code from the app, or a backup code such as ABCD-EFGH."""

    code: str = Field(min_length=6, max_length=20)


class MfaSetupResponse(BaseModel):
    """What the person adds to their app: type the secret, or open or scan the link."""

    secret: str
    otpauth_uri: str


class MfaConfirmedResponse(TokenResponse):
    """Signed in, and the backup codes: shown this once, never again."""

    backup_codes: list[str]


class MeResponse(BaseModel):
    """What we are willing to say about the logged-in person. No password_hash, ever."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str
    role: str
class StaffCreate(BaseModel):
    """The form an admin fills in to add a staff member. No clinic box: it comes from the guard."""

    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=128)


class StaffResponse(BaseModel):
    """What we say about a staff member. No password_hash, ever."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool

class ClinicianResponse(BaseModel):
    """A doctor or nurse to choose from. No email, no account details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    role: str

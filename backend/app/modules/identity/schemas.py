from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """The form a person fills in to log in."""

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """The answer we send back: the wristband."""

    access_token: str
    token_type: str = "bearer"
from __future__ import annotations
from pydantic import BaseModel, Field

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenPairResponse(BaseModel):
    """Standard token response payload for OAuth2-style JWT authentication."""

    access_token: str = Field(..., description="Short-lived JWT access token (type=access).")
    refresh_token: str = Field(..., description="Long-lived JWT refresh token (type=refresh).")
    token_type: str = Field(default="bearer", description="Token type for Authorization header.")
"""
JWT Token Handler - JSON Web Token operations for authentication.

This module handles creation and validation of JWT tokens for user authentication.
Implements RFC 7519 standard claims for security and interoperability.
"""

import uuid
from datetime import datetime, timezone, timedelta
from jose import JWTError, jwt
from typing import Any, Literal
from core.config import get_auth_config


def create_token(data: dict, token_type: Literal["access", "refresh"] = "access") -> str:
    """
    Create a JWT token with standard RFC 7519 claims.
    
    Standard Claims Included:
    - sub (subject): User ID who the token is for
    - iat (issued at): When the token was created
    - exp (expiration): When the token expires
    - jti (JWT ID): Unique identifier for this token
    
    Custom Claims:
    - type: "access" or "refresh" to prevent token confusion
    - username: User's username
    
    Args:
        data: Dictionary containing user information.
              Must include: user_id, username
        token_type: Type of token to create ("access" or "refresh")
              
    Returns:
        str: Encoded JWT token
        
    Raises:
        ValueError: If user_id is missing from data
        
    Example:
        >>> token_data = {"user_id": 123, "username": "johndoe"}
        >>> token = create_token(token_data)
        >>> print(token)
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    """
    config = get_auth_config()

    user_id = data.get("user_id")
    username = data.get("username")
    token_version = data.get("token_version")
    
    if not user_id:
        raise ValueError("user_id is required in token data")
    if not username:
        raise ValueError("username is required in token data")
    if token_version is None:
        raise ValueError("token_version is required in token data")
    
    now = datetime.now(timezone.utc)
    expire = now + (timedelta(minutes=config.access_token_expire_minutes)
                    if token_type == "access"
                    else timedelta(days=config.refresh_token_expire_days))
    
    payload = {
        "sub": str(user_id),          
        "iat": now,   
        "exp": expire, 
        "jti": str(uuid.uuid4()),     
        
        "type": token_type,            
        "username": data.get("username"),
        "token_version": int(token_version),
    }
    
    encoded_jwt = jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)
    
    return encoded_jwt


def decode_token(
    token: str, 
    expected_type: Literal["access", "refresh"] = "access"
) -> dict[str, Any] | None:
    """
    Decode and verify a JWT token.
    
    Validates:
    - Token signature (using SECRET_KEY)
    - Token expiration (exp claim)
    - Token type matches expected type
    
    Args:
        token: JWT token string to decode
        expected_type: Expected token type ("access" or "refresh")
        
    Returns:
        dict: Token payload if valid, containing:
              - sub: User ID (as string)
              - iat: Issued at timestamp
              - exp: Expiration timestamp
              - jti: Unique token ID
              - type: Token type
              - username: User's username
        None: If token is invalid, expired, malformed, or wrong type
        
    Example:
        >>> payload = decode_token(access_token, expected_type="access")
        >>> if payload:
        ...     user_id = int(payload["sub"])
        ...     print(f"Valid token for user {user_id}")
        ... else:
        ...     print("Invalid or expired token")
    """
    config = get_auth_config()
    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=[config.jwt_algorithm])
        
        token_type = payload.get("type")
        if token_type != expected_type:
            return None
        
        return payload
        
    except JWTError:
        return None


def create_access_token(user_data: dict) -> str:
    """
    Create an access token (short-lived).
    
    Convenience wrapper around create_token() for access tokens.
    
    Args:
        user_data: Dict with user_id, username
        
    Returns:
        str: Access token
    """
    return create_token(user_data, token_type="access")


def create_refresh_token(user_data: dict) -> str:
    """
    Create a refresh token (long-lived).
    
    Refresh tokens are used to obtain new access tokens without re-authentication.
    They have much longer expiration (typically 7-30 days).
    
    Security Note:
    - Store refresh token hash in database for revocation
    - Implement token rotation on refresh
    - Add revocation mechanism
    
    Args:
        user_data: Dict with user_id, username
        
    Returns:
        str: Refresh token
    """
    return create_token(user_data, token_type="refresh")

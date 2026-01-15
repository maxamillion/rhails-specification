"""Authentication middleware for FastAPI."""


from fastapi import Header, HTTPException, status
from fastapi.security import HTTPBearer

from src.agent.auth.oauth_validator import OAuthValidator

# Security scheme for Swagger UI
security = HTTPBearer()


class AuthMiddleware:
    """Authentication middleware using OpenShift OAuth."""

    def __init__(self):
        """Initialize auth middleware."""
        self.oauth_validator = OAuthValidator()

    async def verify_token(
        self, authorization: str = Header(None)
    ) -> dict:
        """Verify OAuth token and extract user info.

        Args:
            authorization: Authorization header with Bearer token

        Returns:
            User information dict

        Raises:
            HTTPException: If token is invalid or missing
        """
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract token from header
        token = self.oauth_validator.extract_token_from_header(authorization)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Expected: Bearer <token>",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token
        user_info = await self.oauth_validator.validate_token(token)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user_info


# Global instance
auth_middleware = AuthMiddleware()


async def get_current_user(
    authorization: str = Header(None)
) -> dict:
    """FastAPI dependency for getting current authenticated user.

    Args:
        authorization: Authorization header

    Returns:
        User information dict

    Example:
        @app.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"username": user["username"]}
    """
    return await auth_middleware.verify_token(authorization)


async def get_optional_user(
    authorization: str = Header(None)
) -> dict | None:
    """FastAPI dependency for optional authentication.

    Args:
        authorization: Authorization header

    Returns:
        User information dict if authenticated, None otherwise
    """
    if not authorization:
        return None

    try:
        return await auth_middleware.verify_token(authorization)
    except HTTPException:
        return None

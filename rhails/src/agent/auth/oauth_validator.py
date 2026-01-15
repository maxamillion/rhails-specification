"""OpenShift OAuth token validation."""

import os

import httpx
from jose import jwt


class OAuthValidator:
    """Validates OpenShift OAuth tokens.

    Integrates with OpenShift OAuth server to verify user tokens
    and extract user identity information.
    """

    def __init__(self, oauth_server_url: str | None = None, verify_ssl: bool = True):
        """Initialize OAuth validator.

        Args:
            oauth_server_url: OpenShift OAuth server URL
            verify_ssl: Whether to verify SSL certificates
        """
        self.oauth_server_url = oauth_server_url or os.getenv(
            "OPENSHIFT_OAUTH_URL",
            "https://oauth-openshift.apps.cluster.example.com",
        )
        self.verify_ssl = verify_ssl
        self.http_client = httpx.AsyncClient(verify=verify_ssl)

    async def validate_token(self, token: str) -> dict | None:
        """Validate OAuth token and extract user information.

        Args:
            token: Bearer token from Authorization header

        Returns:
            User information dict with username, uid, groups if valid, None otherwise
        """
        try:
            # Call OpenShift OAuth userinfo endpoint
            response = await self.http_client.get(
                f"{self.oauth_server_url}/oauth/token/info",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )

            if response.status_code != 200:
                return None

            token_info = response.json()

            # Extract user information
            return {
                "username": token_info.get("user", {}).get("name"),
                "uid": token_info.get("user", {}).get("uid"),
                "groups": token_info.get("user", {}).get("groups", []),
                "token": token,
            }

        except (httpx.HTTPError, KeyError):
            return None

    async def validate_service_account_token(self, token: str) -> dict | None:
        """Validate service account token.

        Args:
            token: Service account token

        Returns:
            Service account information if valid, None otherwise
        """
        try:
            # For service accounts, we can decode the JWT without verification
            # in development. In production, use proper key verification.
            payload = jwt.get_unverified_claims(token)

            # Extract service account information
            return {
                "username": payload.get("kubernetes.io/serviceaccount/service-account.name"),
                "namespace": payload.get("kubernetes.io/serviceaccount/namespace"),
                "uid": payload.get("kubernetes.io/serviceaccount/service-account.uid"),
                "token": token,
            }

        except Exception:
            return None

    def extract_token_from_header(self, authorization: str) -> str | None:
        """Extract bearer token from Authorization header.

        Args:
            authorization: Authorization header value

        Returns:
            Token string if valid format, None otherwise
        """
        if not authorization or not authorization.startswith("Bearer "):
            return None

        return authorization[7:]  # Remove "Bearer " prefix

    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()

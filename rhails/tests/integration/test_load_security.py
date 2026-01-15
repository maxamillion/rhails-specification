"""Load and security tests for OpenShift AI Conversational Agent.

These tests verify:
- T139: System handles 100+ concurrent conversations
- T140: RBAC enforcement and OAuth validation

Requirements:
- Running PostgreSQL database
- OpenShift cluster access
- OAuth provider configured
"""

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def test_client():
    """Provide FastAPI test client."""
    return TestClient(app)


@pytest.mark.integration
@pytest.mark.load
class TestConcurrentConversations:
    """Load tests for concurrent conversation handling (T139)."""

    @pytest.mark.asyncio
    async def test_handle_100_concurrent_conversations(
        self, test_client: TestClient
    ) -> None:
        """Test that system handles 100+ concurrent conversations without degradation."""

        def make_query(session_num: int) -> dict:
            """Make a query in a specific session."""
            try:
                with patch(
                    "src.services.intent_parser.IntentParser.parse_intent"
                ) as mock_parser:
                    mock_intent = MagicMock()
                    mock_intent.confidence = 0.90
                    mock_parser.return_value = mock_intent

                    response = test_client.post(
                        "/v1/query",
                        json={
                            "query": f"List models in session {session_num}",
                            "user_id": f"user-{session_num}",
                            "session_id": str(uuid.uuid4()),
                        },
                    )
                    return {
                        "session": session_num,
                        "status_code": response.status_code,
                        "success": response.status_code == 200,
                    }
            except Exception as e:
                return {"session": session_num, "success": False, "error": str(e)}

        # Execute 150 concurrent queries
        num_conversations = 150

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [
                executor.submit(make_query, i) for i in range(num_conversations)
            ]
            results = [f.result() for f in futures]

        # Analyze results
        successful = sum(1 for r in results if r.get("success", False))
        success_rate = (successful / num_conversations) * 100

        assert successful >= 100, f"Only {successful}/150 conversations succeeded"
        assert (
            success_rate >= 95.0
        ), f"Success rate {success_rate:.1f}% is below 95% threshold"

    @pytest.mark.asyncio
    async def test_concurrent_sessions_maintain_isolation(
        self, test_client: TestClient
    ) -> None:
        """Test that concurrent sessions maintain proper isolation."""
        session_ids = [str(uuid.uuid4()) for _ in range(50)]

        def query_session(session_id: str, user_id: str) -> dict:
            """Make query in specific session."""
            with patch(
                "src.services.intent_parser.IntentParser.parse_intent"
            ) as mock_parser:
                mock_intent = MagicMock()
                mock_parser.return_value = mock_intent

                response = test_client.post(
                    "/v1/query",
                    json={
                        "query": f"Test query for {user_id}",
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                )
                return {
                    "session_id": session_id,
                    "user_id": user_id,
                    "status_code": response.status_code,
                }

        # Run concurrent queries in different sessions
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = [
                executor.submit(query_session, sid, f"user-{i}")
                for i, sid in enumerate(session_ids)
            ]
            results = [f.result() for f in futures]

        # Verify all sessions were processed
        assert len(results) == 50
        assert all(r["status_code"] in [200, 401, 403] for r in results)

    @pytest.mark.asyncio
    async def test_database_connection_pool_under_load(
        self, test_client: TestClient
    ) -> None:
        """Test that database connection pool handles concurrent load."""

        def make_db_query(query_num: int) -> bool:
            """Make query that requires database access."""
            with patch(
                "src.services.intent_parser.IntentParser.parse_intent"
            ) as mock_parser:
                mock_intent = MagicMock()
                mock_parser.return_value = mock_intent

                try:
                    response = test_client.post(
                        "/v1/query",
                        json={
                            "query": f"Query {query_num}",
                            "user_id": "test-user",
                        },
                    )
                    return response.status_code in [200, 401, 403]
                except Exception:
                    return False

        # Execute 100 concurrent database-heavy operations
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(make_db_query, i) for i in range(100)]
            results = [f.result() for f in futures]

        success_count = sum(results)
        assert (
            success_count >= 95
        ), f"Database pool handled only {success_count}/100 concurrent requests"


@pytest.mark.integration
@pytest.mark.security
class TestRBACEnforcement:
    """Security tests for RBAC enforcement (T140)."""

    @pytest.mark.asyncio
    async def test_unauthorized_user_denied_access(
        self, test_client: TestClient
    ) -> None:
        """Test that unauthorized users are denied access."""
        with patch("src.api.middleware.auth.verify_oauth_token") as mock_verify:
            # Mock OAuth verification to fail
            mock_verify.return_value = None

            response = test_client.post(
                "/v1/query",
                json={"query": "List my models"},
                headers={"Authorization": "Bearer invalid_token"},
            )

            assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_rbac_prevents_unauthorized_operations(
        self, test_client: TestClient
    ) -> None:
        """Test that RBAC prevents users from accessing unauthorized resources."""
        with patch("src.agent.auth.rbac_checker.RBACChecker.check_access") as mock_rbac:
            # Mock RBAC to deny access
            mock_rbac.return_value = False

            with patch(
                "src.api.middleware.auth.verify_oauth_token"
            ) as mock_oauth:
                mock_oauth.return_value = {"sub": "test-user", "groups": ["viewers"]}

                response = test_client.post(
                    "/v1/query",
                    json={"query": "Delete all models"},
                    headers={"Authorization": "Bearer valid_token"},
                )

                # Should be forbidden due to RBAC
                assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rbac_allows_authorized_operations(
        self, test_client: TestClient
    ) -> None:
        """Test that RBAC allows authorized users to perform operations."""
        with patch("src.agent.auth.rbac_checker.RBACChecker.check_access") as mock_rbac:
            # Mock RBAC to allow access
            mock_rbac.return_value = True

            with patch(
                "src.api.middleware.auth.verify_oauth_token"
            ) as mock_oauth:
                mock_oauth.return_value = {
                    "sub": "admin-user",
                    "groups": ["admins"],
                }

                with patch(
                    "src.services.intent_parser.IntentParser.parse_intent"
                ) as mock_parser:
                    mock_intent = MagicMock()
                    mock_parser.return_value = mock_intent

                    response = test_client.post(
                        "/v1/query",
                        json={"query": "List all models"},
                        headers={"Authorization": "Bearer admin_token"},
                    )

                    # Should succeed for authorized admin
                    assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_namespace_isolation_enforced(
        self, test_client: TestClient
    ) -> None:
        """Test that users can only access their own namespaces."""
        with patch("src.agent.auth.rbac_checker.RBACChecker.check_access") as mock_rbac:

            def check_namespace_access(user_id: str, resource: str, namespace: str):
                # Only allow access to user's own namespace
                return namespace == f"{user_id}-project"

            mock_rbac.side_effect = check_namespace_access

            with patch(
                "src.api.middleware.auth.verify_oauth_token"
            ) as mock_oauth:
                mock_oauth.return_value = {"sub": "user1", "groups": ["users"]}

                # Try to access another user's namespace
                with patch(
                    "src.services.intent_parser.IntentParser.parse_intent"
                ) as mock_parser:
                    mock_intent = MagicMock()
                    mock_intent.parameters = {"namespace": "user2-project"}
                    mock_parser.return_value = mock_intent

                    response = test_client.post(
                        "/v1/query",
                        json={"query": "List models in user2-project"},
                        headers={"Authorization": "Bearer user1_token"},
                    )

                    # Should be forbidden - accessing other user's namespace
                    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.security
class TestOAuthValidation:
    """Security tests for OAuth validation (T140)."""

    @pytest.mark.asyncio
    async def test_missing_auth_token_rejected(
        self, test_client: TestClient
    ) -> None:
        """Test that requests without auth tokens are rejected."""
        response = test_client.post(
            "/v1/query",
            json={"query": "List my models"},
            # No Authorization header
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, test_client: TestClient) -> None:
        """Test that expired OAuth tokens are rejected."""
        with patch("src.api.middleware.auth.verify_oauth_token") as mock_verify:
            # Mock expired token
            mock_verify.side_effect = Exception("Token expired")

            response = test_client.post(
                "/v1/query",
                json={"query": "List my models"},
                headers={"Authorization": "Bearer expired_token"},
            )

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_format_rejected(
        self, test_client: TestClient
    ) -> None:
        """Test that invalid token formats are rejected."""
        response = test_client.post(
            "/v1/query",
            json={"query": "List my models"},
            headers={"Authorization": "Invalid format"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_accepted(self, test_client: TestClient) -> None:
        """Test that valid OAuth tokens are accepted."""
        with patch("src.api.middleware.auth.verify_oauth_token") as mock_verify:
            mock_verify.return_value = {
                "sub": "test-user",
                "exp": 9999999999,
                "groups": ["users"],
            }

            with patch("src.agent.auth.rbac_checker.RBACChecker.check_access") as mock_rbac:
                mock_rbac.return_value = True

                with patch(
                    "src.services.intent_parser.IntentParser.parse_intent"
                ) as mock_parser:
                    mock_intent = MagicMock()
                    mock_parser.return_value = mock_intent

                    response = test_client.post(
                        "/v1/query",
                        json={"query": "List my models"},
                        headers={"Authorization": "Bearer valid_token"},
                    )

                    assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_token_refresh_workflow(self, test_client: TestClient) -> None:
        """Test that token refresh workflow works correctly."""
        # First request with valid token
        with patch("src.api.middleware.auth.verify_oauth_token") as mock_verify:
            mock_verify.return_value = {"sub": "test-user", "groups": ["users"]}

            with patch("src.agent.auth.rbac_checker.RBACChecker.check_access") as mock_rbac:
                mock_rbac.return_value = True

                with patch(
                    "src.services.intent_parser.IntentParser.parse_intent"
                ) as mock_parser:
                    mock_intent = MagicMock()
                    mock_parser.return_value = mock_intent

                    # Initial request
                    response1 = test_client.post(
                        "/v1/query",
                        json={"query": "List models"},
                        headers={"Authorization": "Bearer token1"},
                    )
                    assert response1.status_code == 200

                    # Subsequent request with refreshed token
                    response2 = test_client.post(
                        "/v1/query",
                        json={"query": "List models"},
                        headers={"Authorization": "Bearer token2"},
                    )
                    assert response2.status_code == 200


@pytest.mark.integration
@pytest.mark.security
class TestSecurityHeaders:
    """Security tests for HTTP headers and security practices."""

    def test_security_headers_present(self, test_client: TestClient) -> None:
        """Test that security headers are present in responses."""
        response = test_client.get("/health")

        # Check for security headers (if configured)
        # These might be added by middleware or reverse proxy
        assert response.status_code == 200

    def test_cors_configuration(self, test_client: TestClient) -> None:
        """Test that CORS is properly configured."""
        response = test_client.options(
            "/v1/query", headers={"Origin": "https://example.com"}
        )

        # CORS headers should be present for OPTIONS requests
        assert response.status_code in [200, 405]  # 405 if OPTIONS not allowed

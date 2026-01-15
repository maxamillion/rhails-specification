"""Unit tests for error translation service."""

import pytest

from src.services.error_translator import ErrorTranslator


@pytest.mark.unit
class TestKubernetesErrorTranslation:
    """Unit tests for Kubernetes API error translation."""

    def test_translate_400_bad_request_with_invalid_data(self) -> None:
        """Test 400 error translation for invalid data."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=400,
            reason="BadRequest",
            message="Invalid field value",
        )

        assert "invalid data" in result.lower()
        assert "check your" in result.lower()

    def test_translate_400_bad_request_generic(self) -> None:
        """Test 400 error translation without specific message."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=400,
            reason="BadRequest",
            message=None,
        )

        assert "not valid" in result.lower()
        assert "verify" in result.lower()

    def test_translate_401_unauthorized(self) -> None:
        """Test 401 error translation."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=401,
            reason="Unauthorized",
            message="Authentication required",
        )

        assert "authentication" in result.lower()
        assert "expired" in result.lower()
        assert "log in" in result.lower()

    def test_translate_403_forbidden_quota_exceeded(self) -> None:
        """Test 403 error translation for quota errors."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=403,
            reason="Forbidden",
            message="Exceeded quota",
        )

        assert "quota" in result.lower()
        assert "delete unused" in result.lower()

    def test_translate_403_forbidden_permission_denied(self) -> None:
        """Test 403 error translation for permission errors."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=403,
            reason="Forbidden",
            message="Permission denied for this operation",
        )

        assert "permission" in result.lower()
        assert "administrator" in result.lower()

    def test_translate_403_forbidden_generic(self) -> None:
        """Test 403 error translation without specific message."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=403,
            reason="Forbidden",
            message=None,
        )

        assert "access denied" in result.lower()
        assert "permission" in result.lower()

    def test_translate_404_not_found_namespace(self) -> None:
        """Test 404 error translation for namespace not found."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=404,
            reason="NotFound",
            message="Namespace 'my-project' not found",
        )

        assert "namespace" in result.lower()
        assert "project" in result.lower()
        assert "check the project name" in result.lower()

    def test_translate_404_not_found_generic(self) -> None:
        """Test 404 error translation for resource not found."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=404,
            reason="NotFound",
            message=None,
        )

        assert "not found" in result.lower()
        assert "verify" in result.lower()

    def test_translate_409_conflict_already_exists(self) -> None:
        """Test 409 error translation for resource already exists."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=409,
            reason="Conflict",
            message="Resource already exists",
        )

        assert "already exists" in result.lower()
        assert "different name" in result.lower()

    def test_translate_409_conflict_being_deleted(self) -> None:
        """Test 409 error translation for resource being deleted."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=409,
            reason="Conflict",
            message="Resource is being deleted",
        )

        assert "being deleted" in result.lower()
        assert "wait" in result.lower()

    def test_translate_409_conflict_generic(self) -> None:
        """Test 409 error translation for generic conflict."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=409,
            reason="Conflict",
            message=None,
        )

        assert "conflicts" in result.lower()
        assert "current state" in result.lower()

    def test_translate_422_unprocessable_validation_error(self) -> None:
        """Test 422 error translation for validation errors."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=422,
            reason="UnprocessableEntity",
            message="Validation failed for field 'replicas'",
        )

        assert "not valid" in result.lower()
        assert "required fields" in result.lower()

    def test_translate_422_unprocessable_generic(self) -> None:
        """Test 422 error translation for generic processing error."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=422,
            reason="UnprocessableEntity",
            message=None,
        )

        assert "could not be processed" in result.lower()
        assert "verify" in result.lower()

    def test_translate_429_rate_limit(self) -> None:
        """Test 429 error translation for rate limiting."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=429,
            reason="TooManyRequests",
            message="Rate limit exceeded",
        )

        assert "too many requests" in result.lower()
        assert "wait" in result.lower()

    def test_translate_500_internal_error(self) -> None:
        """Test 500 error translation for internal server errors."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=500,
            reason="InternalServerError",
            message="Internal error occurred",
        )

        assert "internal error" in result.lower()
        assert "try again" in result.lower()
        assert "support" in result.lower()

    def test_translate_503_service_unavailable(self) -> None:
        """Test 503 error translation for service unavailable."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=503,
            reason="ServiceUnavailable",
            message="Service temporarily unavailable",
        )

        assert "unavailable" in result.lower()
        assert "temporarily" in result.lower()
        assert "try again" in result.lower()

    def test_translate_unknown_status_code(self) -> None:
        """Test error translation for unknown status code."""
        result = ErrorTranslator.translate_kubernetes_error(
            status_code=418,  # I'm a teapot
            reason="TeapotError",
            message="Cannot brew coffee",
        )

        assert "TeapotError" in result
        assert "try again" in result.lower()


@pytest.mark.unit
class TestOperationErrorTranslation:
    """Unit tests for operation-specific error translation."""

    def test_translate_create_already_exists(self) -> None:
        """Test create operation error when resource already exists."""
        error = Exception("resource already exists in namespace")

        result = ErrorTranslator.translate_operation_error(
            operation="create",
            resource_type="model",
            resource_name="fraud-detector",
            error=error,
        )

        assert "fraud-detector" in result
        assert "already exists" in result.lower()
        assert "different name" in result.lower()

    def test_translate_deploy_quota_exceeded(self) -> None:
        """Test deploy operation error for quota exceeded."""
        error = Exception("exceeded quota for resource requests.cpu")

        result = ErrorTranslator.translate_operation_error(
            operation="deploy",
            resource_type="model",
            resource_name="sentiment-analyzer",
            error=error,
        )

        assert "sentiment-analyzer" in result
        assert ("quota" in result.lower() or "insufficient resources" in result.lower())

    def test_translate_create_image_pull_error(self) -> None:
        """Test create operation error for image pull failure."""
        error = Exception("image pull failed: access denied")

        result = ErrorTranslator.translate_operation_error(
            operation="create",
            resource_type="model",
            resource_name="recommendation-engine",
            error=error,
        )

        assert "recommendation-engine" in result
        assert "image" in result.lower()
        assert "storage uri" in result.lower()

    def test_translate_delete_not_found(self) -> None:
        """Test delete operation error when resource not found."""
        error = Exception("resource not found")

        result = ErrorTranslator.translate_operation_error(
            operation="delete",
            resource_type="notebook",
            resource_name="experiment-notebook",
            error=error,
        )

        assert "experiment-notebook" in result
        assert ("not found" in result.lower() or "doesn't exist" in result.lower())

    def test_translate_delete_protected_resource(self) -> None:
        """Test delete operation error for protected resource."""
        error = Exception("resource has finalizer protection")

        result = ErrorTranslator.translate_operation_error(
            operation="remove",
            resource_type="pipeline",
            resource_name="data-prep-pipeline",
            error=error,
        )

        assert "data-prep-pipeline" in result
        assert "protected" in result.lower()
        assert "dependencies" in result.lower()

    def test_translate_scale_not_found(self) -> None:
        """Test scale operation error when resource not found."""
        error = Exception("InferenceService not found")

        result = ErrorTranslator.translate_operation_error(
            operation="scale",
            resource_type="model",
            resource_name="churn-predictor",
            error=error,
        )

        assert "churn-predictor" in result
        assert ("not found" in result.lower() or "doesn't exist" in result.lower())

    def test_translate_scale_invalid_replica_count(self) -> None:
        """Test scale operation error for invalid replica count."""
        error = Exception("replica count must be between 0 and 10")

        result = ErrorTranslator.translate_operation_error(
            operation="scale",
            resource_type="model",
            resource_name="fraud-detector",
            error=error,
        )

        assert "fraud-detector" in result
        assert "replica" in result.lower()
        assert "valid replica count" in result.lower()

    def test_translate_update_not_found(self) -> None:
        """Test update operation error when resource not found."""
        error = Exception("resource not found in namespace")

        result = ErrorTranslator.translate_operation_error(
            operation="update",
            resource_type="pipeline",
            resource_name="training-pipeline",
            error=error,
        )

        assert "training-pipeline" in result
        assert ("not found" in result.lower() or "doesn't exist" in result.lower())

    def test_translate_generic_operation_error(self) -> None:
        """Test generic operation error translation."""
        error = Exception("Unknown error occurred")

        result = ErrorTranslator.translate_operation_error(
            operation="patch",
            resource_type="project",
            resource_name="ml-team",
            error=error,
        )

        assert "ml-team" in result
        assert "patch" in result.lower()
        assert "project" in result.lower()
        assert "Unknown error occurred" in result

    def test_translate_operation_error_preserves_resource_context(self) -> None:
        """Test that operation error translation includes all resource context."""
        error = Exception("Custom error message")

        result = ErrorTranslator.translate_operation_error(
            operation="test",
            resource_type="custom-resource",
            resource_name="my-resource",
            error=error,
        )

        # Should include operation, resource type, resource name, and error
        assert "test" in result.lower()
        assert "custom-resource" in result
        assert "my-resource" in result
        assert "Custom error message" in result

"""Error message translation service.

This service translates technical OpenShift API errors into user-friendly
messages that are actionable and easy to understand.
"""



class ErrorTranslator:
    """Translate technical errors to user-friendly messages."""

    @staticmethod
    def translate_kubernetes_error(
        status_code: int,
        reason: str,
        message: str | None = None,
    ) -> str:
        """Translate Kubernetes API error to user-friendly message.

        Args:
            status_code: HTTP status code from Kubernetes API
            reason: Error reason from Kubernetes
            message: Detailed error message (optional)

        Returns:
            User-friendly error message with actionable guidance
        """
        # Map common status codes to user-friendly messages
        error_messages = {
            400: ErrorTranslator._handle_400_bad_request,
            401: ErrorTranslator._handle_401_unauthorized,
            403: ErrorTranslator._handle_403_forbidden,
            404: ErrorTranslator._handle_404_not_found,
            409: ErrorTranslator._handle_409_conflict,
            422: ErrorTranslator._handle_422_unprocessable,
            429: ErrorTranslator._handle_429_rate_limit,
            500: ErrorTranslator._handle_500_internal_error,
            503: ErrorTranslator._handle_503_unavailable,
        }

        handler = error_messages.get(status_code)
        if handler:
            return handler(reason, message)

        # Generic error message
        return f"OpenShift AI error: {reason}. Please try again or contact support."

    @staticmethod
    def _handle_400_bad_request(reason: str, message: str | None) -> str:
        """Handle 400 Bad Request errors."""
        if message and "invalid" in message.lower():
            return (
                "The request contains invalid data. "
                "Please check your model name, namespace, and configuration parameters."
            )
        return (
            "The request is not valid. "
            "Please verify all required parameters are provided correctly."
        )

    @staticmethod
    def _handle_401_unauthorized(reason: str, message: str | None) -> str:
        """Handle 401 Unauthorized errors."""
        return (
            "Your authentication session has expired. "
            "Please log in again to continue using OpenShift AI."
        )

    @staticmethod
    def _handle_403_forbidden(reason: str, message: str | None) -> str:
        """Handle 403 Forbidden errors."""
        if message and "quota" in message.lower():
            return (
                "You have exceeded your resource quota. "
                "Please delete unused resources or request a quota increase from your administrator."
            )

        if message and "permission" in message.lower():
            return (
                "You don't have permission to perform this operation. "
                "Please contact your OpenShift AI administrator to request access."
            )

        return (
            "Access denied. You don't have permission to perform this operation on this resource. "
            "Contact your administrator if you believe this is an error."
        )

    @staticmethod
    def _handle_404_not_found(reason: str, message: str | None) -> str:
        """Handle 404 Not Found errors."""
        if message and "namespace" in message.lower():
            return (
                "The specified project/namespace was not found. "
                "Please check the project name or create a new project first."
            )

        return (
            "The requested resource was not found in OpenShift AI. "
            "Please verify the resource name and try again."
        )

    @staticmethod
    def _handle_409_conflict(reason: str, message: str | None) -> str:
        """Handle 409 Conflict errors."""
        if message and "already exists" in message.lower():
            return (
                "A resource with this name already exists. "
                "Please choose a different name or delete the existing resource first."
            )

        if message and "being deleted" in message.lower():
            return (
                "This resource is currently being deleted. "
                "Please wait a few moments and try again."
            )

        return (
            "The operation conflicts with the current state of the resource. "
            "Please refresh and try again."
        )

    @staticmethod
    def _handle_422_unprocessable(reason: str, message: str | None) -> str:
        """Handle 422 Unprocessable Entity errors."""
        if message and "validation" in message.lower():
            return (
                "The resource configuration is not valid. "
                "Please check that all required fields are provided and values are within acceptable ranges."
            )

        return (
            "The resource configuration could not be processed. "
            "Please verify your configuration matches the required format."
        )

    @staticmethod
    def _handle_429_rate_limit(reason: str, message: str | None) -> str:
        """Handle 429 Too Many Requests errors."""
        return (
            "You have made too many requests. "
            "Please wait a few moments before trying again."
        )

    @staticmethod
    def _handle_500_internal_error(reason: str, message: str | None) -> str:
        """Handle 500 Internal Server Error."""
        return (
            "OpenShift AI encountered an internal error. "
            "Please try again in a few moments. If the problem persists, contact support."
        )

    @staticmethod
    def _handle_503_unavailable(reason: str, message: str | None) -> str:
        """Handle 503 Service Unavailable errors."""
        return (
            "OpenShift AI is temporarily unavailable. "
            "This is usually brief. Please try again in a few moments."
        )

    @staticmethod
    def translate_operation_error(
        operation: str,
        resource_type: str,
        resource_name: str,
        error: Exception,
    ) -> str:
        """Translate operation-specific errors to user-friendly messages.

        Args:
            operation: Operation type (create, update, delete, etc.)
            resource_type: Type of resource (model, pipeline, notebook, etc.)
            resource_name: Name of the resource
            error: The exception that occurred

        Returns:
            User-friendly error message with context
        """
        error_str = str(error).lower()

        # Check for common operation-specific errors
        if operation == "create" or operation == "deploy":
            if "already exists" in error_str:
                return (
                    f"Cannot deploy '{resource_name}' because a {resource_type} with this name already exists. "
                    f"Please choose a different name or delete the existing {resource_type}."
                )
            if "quota" in error_str:
                return (
                    f"Cannot deploy '{resource_name}' due to insufficient resources. "
                    f"Please delete unused {resource_type}s or request additional capacity."
                )
            if "image" in error_str and "pull" in error_str:
                return (
                    f"Cannot deploy '{resource_name}' because the model image could not be downloaded. "
                    f"Please verify the storage URI is accessible."
                )

        elif operation == "delete" or operation == "remove":
            if "not found" in error_str:
                return (
                    f"Cannot delete '{resource_name}' because it doesn't exist. "
                    f"It may have already been deleted."
                )
            if "protected" in error_str or "finalizer" in error_str:
                return (
                    f"Cannot delete '{resource_name}' because it's protected or has dependencies. "
                    f"Please remove dependent resources first."
                )

        elif operation == "scale" or operation == "update":
            if "not found" in error_str:
                return (
                    f"Cannot scale '{resource_name}' because it doesn't exist. "
                    f"Please deploy it first."
                )
            if "replica" in error_str:
                return (
                    f"Cannot scale '{resource_name}' to the requested replica count. "
                    f"Please choose a valid replica count between 0 and 10."
                )

        # Generic operation error
        return (
            f"Failed to {operation} {resource_type} '{resource_name}': {str(error)}. "
            f"Please verify the {resource_type} exists and you have permission to {operation} it."
        )

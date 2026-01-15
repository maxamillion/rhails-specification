"""RBAC permission checker for OpenShift resources."""


from kubernetes import client
from kubernetes.client.rest import ApiException


class RBACChecker:
    """Checks user RBAC permissions for OpenShift resources.

    Validates whether a user has permission to perform operations
    on specific Kubernetes resources based on their role bindings.
    """

    def __init__(self, auth_api: client.AuthorizationV1Api):
        """Initialize RBAC checker.

        Args:
            auth_api: Kubernetes AuthorizationV1Api client
        """
        self.auth_api = auth_api

    async def can_user_perform(
        self,
        user: str,
        verb: str,
        group: str,
        resource: str,
        namespace: str | None = None,
        resource_name: str | None = None,
    ) -> bool:
        """Check if user can perform action on resource.

        Args:
            user: Username
            verb: Action verb (get, list, create, update, delete, etc.)
            group: API group (e.g., "serving.kserve.io")
            resource: Resource type plural (e.g., "inferenceservices")
            namespace: Target namespace (for namespaced resources)
            resource_name: Specific resource name (optional)

        Returns:
            True if user has permission, False otherwise
        """
        # Build SubjectAccessReview request
        resource_attributes = client.V1ResourceAttributes(
            verb=verb,
            group=group,
            resource=resource,
            namespace=namespace,
            name=resource_name,
        )

        sar = client.V1SubjectAccessReview(
            spec=client.V1SubjectAccessReviewSpec(
                user=user,
                resource_attributes=resource_attributes,
            )
        )

        try:
            # Submit SubjectAccessReview
            result = self.auth_api.create_subject_access_review(body=sar)

            # Check if access is allowed
            return result.status.allowed

        except ApiException:
            # On error, deny access
            return False

    async def get_user_namespaces(self, user: str) -> list[str]:
        """Get list of namespaces user has access to.

        Args:
            user: Username

        Returns:
            List of accessible namespace names
        """
        # This is a simplified implementation
        # In production, you might want to cache this or use a more efficient approach
        try:
            # Try to list all namespaces the user can see
            core_v1 = client.CoreV1Api()
            namespaces = core_v1.list_namespace()

            accessible_namespaces = []
            for ns in namespaces.items:
                ns_name = ns.metadata.name

                # Check if user can list pods in this namespace as a proxy for access
                if await self.can_user_perform(
                    user=user,
                    verb="list",
                    group="",
                    resource="pods",
                    namespace=ns_name,
                ):
                    accessible_namespaces.append(ns_name)

            return accessible_namespaces

        except ApiException:
            return []

    async def get_user_permissions(
        self, user: str, namespace: str
    ) -> dict[str, list[str]]:
        """Get user's permissions for common OpenShift AI resources in namespace.

        Args:
            user: Username
            namespace: Target namespace

        Returns:
            Dict mapping resource types to allowed verbs
        """
        resources = {
            "inferenceservices": "serving.kserve.io",
            "notebooks": "kubeflow.org",
            "pipelines": "kubeflow.org",
        }

        verbs = ["get", "list", "create", "update", "patch", "delete"]

        permissions = {}

        for resource, group in resources.items():
            allowed_verbs = []

            for verb in verbs:
                if await self.can_user_perform(
                    user=user,
                    verb=verb,
                    group=group,
                    resource=resource,
                    namespace=namespace,
                ):
                    allowed_verbs.append(verb)

            if allowed_verbs:
                permissions[resource] = allowed_verbs

        return permissions

    async def require_permission(
        self,
        user: str,
        verb: str,
        group: str,
        resource: str,
        namespace: str | None = None,
        resource_name: str | None = None,
    ) -> None:
        """Require user permission, raise exception if denied.

        Args:
            user: Username
            verb: Action verb
            group: API group
            resource: Resource type
            namespace: Target namespace
            resource_name: Specific resource name

        Raises:
            PermissionError: If user lacks permission
        """
        has_permission = await self.can_user_perform(
            user=user,
            verb=verb,
            group=group,
            resource=resource,
            namespace=namespace,
            resource_name=resource_name,
        )

        if not has_permission:
            resource_path = f"{group}/{resource}"
            if namespace:
                resource_path = f"{namespace}/{resource_path}"
            if resource_name:
                resource_path = f"{resource_path}/{resource_name}"

            raise PermissionError(
                f"User '{user}' does not have permission to '{verb}' {resource_path}"
            )

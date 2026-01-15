"""OpenShift API client wrapper for managing OpenShift AI resources."""

import os

from kubernetes import client, config
from kubernetes.client.rest import ApiException


class OpenShiftClient:
    """Wrapper for OpenShift/Kubernetes API client.

    Provides methods to interact with OpenShift AI resources including
    InferenceServices (KServe), Notebooks, Pipelines, and Projects.
    """

    def __init__(
        self,
        api_url: str | None = None,
        token: str | None = None,
        verify_ssl: bool = True,
    ):
        """Initialize OpenShift client.

        Args:
            api_url: OpenShift API URL (defaults to OPENSHIFT_API_URL env var)
            token: Service account token (defaults to reading from token_path)
            verify_ssl: Whether to verify SSL certificates
        """
        self.api_url = api_url or os.getenv(
            "OPENSHIFT_API_URL", "https://kubernetes.default.svc"
        )
        self.verify_ssl = verify_ssl

        # Try to load token from environment or file
        if token is None:
            token = os.getenv("OPENSHIFT_TOKEN")
            if token is None:
                token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
                if os.path.exists(token_path):
                    with open(token_path) as f:
                        token = f.read().strip()

        self.token = token
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Kubernetes API client configuration."""
        try:
            # Try in-cluster configuration first
            config.load_incluster_config()
        except config.ConfigException:
            try:
                # Fall back to kubeconfig
                config.load_kube_config()
            except config.ConfigException:
                # Manual configuration
                configuration = client.Configuration()
                configuration.host = self.api_url
                configuration.verify_ssl = self.verify_ssl
                if self.token:
                    configuration.api_key = {"authorization": f"Bearer {self.token}"}
                client.Configuration.set_default(configuration)

        # Initialize API clients
        self.core_v1 = client.CoreV1Api()
        self.custom_objects = client.CustomObjectsApi()
        self.rbac_v1 = client.RbacAuthorizationV1Api()

    # ========== InferenceService Operations (KServe) ==========

    async def create_inference_service(
        self,
        name: str,
        namespace: str,
        predictor_config: dict,
        replicas: int = 1,
        metadata: dict | None = None,
    ) -> dict:
        """Create a KServe InferenceService for model deployment.

        Args:
            name: InferenceService name
            namespace: Target namespace
            predictor_config: Predictor configuration (model location, runtime, etc.)
            replicas: Number of replicas
            metadata: Additional metadata (labels, annotations)

        Returns:
            Created InferenceService resource

        Raises:
            ApiException: If creation fails
        """
        body = {
            "apiVersion": "serving.kserve.io/v1beta1",
            "kind": "InferenceService",
            "metadata": {
                "name": name,
                "namespace": namespace,
                **(metadata or {}),
            },
            "spec": {
                "predictor": {
                    **predictor_config,
                    "minReplicas": replicas,
                    "maxReplicas": replicas,
                }
            },
        }

        return self.custom_objects.create_namespaced_custom_object(
            group="serving.kserve.io",
            version="v1beta1",
            namespace=namespace,
            plural="inferenceservices",
            body=body,
        )

    async def get_inference_service(self, name: str, namespace: str) -> dict:
        """Get InferenceService details.

        Args:
            name: InferenceService name
            namespace: Target namespace

        Returns:
            InferenceService resource

        Raises:
            ApiException: If not found or access denied
        """
        return self.custom_objects.get_namespaced_custom_object(
            group="serving.kserve.io",
            version="v1beta1",
            namespace=namespace,
            plural="inferenceservices",
            name=name,
        )

    async def list_inference_services(self, namespace: str) -> list[dict]:
        """List all InferenceServices in namespace.

        Args:
            namespace: Target namespace

        Returns:
            List of InferenceService resources
        """
        result = self.custom_objects.list_namespaced_custom_object(
            group="serving.kserve.io",
            version="v1beta1",
            namespace=namespace,
            plural="inferenceservices",
        )
        return result.get("items", [])

    async def patch_inference_service(
        self, name: str, namespace: str, patch_data: dict
    ) -> dict:
        """Patch InferenceService with custom data.

        Args:
            name: InferenceService name
            namespace: Target namespace
            patch_data: Patch data to apply

        Returns:
            Updated InferenceService resource
        """
        return self.custom_objects.patch_namespaced_custom_object(
            group="serving.kserve.io",
            version="v1beta1",
            namespace=namespace,
            plural="inferenceservices",
            name=name,
            body=patch_data,
        )

    async def scale_inference_service(
        self, name: str, namespace: str, replicas: int
    ) -> dict:
        """Scale InferenceService replicas.

        Args:
            name: InferenceService name
            namespace: Target namespace
            replicas: New replica count

        Returns:
            Updated InferenceService resource
        """
        patch = {
            "spec": {
                "predictor": {
                    "minReplicas": replicas,
                    "maxReplicas": replicas,
                }
            }
        }

        return await self.patch_inference_service(name, namespace, patch)

    async def delete_inference_service(self, name: str, namespace: str) -> dict:
        """Delete InferenceService.

        Args:
            name: InferenceService name
            namespace: Target namespace

        Returns:
            Deletion status
        """
        return self.custom_objects.delete_namespaced_custom_object(
            group="serving.kserve.io",
            version="v1beta1",
            namespace=namespace,
            plural="inferenceservices",
            name=name,
        )

    # ========== Notebook Operations ==========

    async def create_notebook(
        self,
        name: str,
        namespace: str,
        image: str,
        memory: str = "4Gi",
        cpu: str = "2",
        volume_size: str = "10Gi",
        metadata: dict | None = None,
    ) -> dict:
        """Create a Kubeflow Notebook workbench.

        Args:
            name: Notebook name
            namespace: Target namespace
            image: Container image (e.g., "jupyter/scipy-notebook:latest")
            memory: Memory request (e.g., "4Gi")
            cpu: CPU request (e.g., "2")
            volume_size: Persistent volume size
            metadata: Additional metadata

        Returns:
            Created Notebook resource
        """
        body = {
            "apiVersion": "kubeflow.org/v1",
            "kind": "Notebook",
            "metadata": {
                "name": name,
                "namespace": namespace,
                **(metadata or {}),
            },
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": name,
                                "image": image,
                                "resources": {
                                    "requests": {
                                        "memory": memory,
                                        "cpu": cpu,
                                    }
                                },
                            }
                        ],
                        "volumes": [
                            {
                                "name": "workspace",
                                "persistentVolumeClaim": {
                                    "claimName": f"{name}-pvc"
                                },
                            }
                        ],
                    }
                }
            },
        }

        return self.custom_objects.create_namespaced_custom_object(
            group="kubeflow.org",
            version="v1",
            namespace=namespace,
            plural="notebooks",
            body=body,
        )

    async def list_notebooks(self, namespace: str) -> list[dict]:
        """List all Notebooks in namespace.

        Args:
            namespace: Target namespace

        Returns:
            List of Notebook resources
        """
        result = self.custom_objects.list_namespaced_custom_object(
            group="kubeflow.org",
            version="v1",
            namespace=namespace,
            plural="notebooks",
        )
        return result.get("items", [])

    async def patch_notebook(
        self, name: str, namespace: str, spec_patch: dict
    ) -> dict:
        """Patch a Notebook resource.

        Args:
            name: Notebook name
            namespace: Target namespace
            spec_patch: Patch to apply to the Notebook spec

        Returns:
            Patched Notebook resource
        """
        return self.custom_objects.patch_namespaced_custom_object(
            group="kubeflow.org",
            version="v1",
            namespace=namespace,
            plural="notebooks",
            name=name,
            body=spec_patch,
        )

    async def start_notebook(self, name: str, namespace: str) -> dict:
        """Start a stopped Notebook.

        Args:
            name: Notebook name
            namespace: Target namespace

        Returns:
            Updated Notebook resource
        """
        # Remove the stop annotation to start the notebook
        patch = {
            "metadata": {
                "annotations": {
                    "kubeflow-resource-stopped": None
                }
            }
        }
        return await self.patch_notebook(name, namespace, patch)

    async def delete_notebook(self, name: str, namespace: str) -> dict:
        """Delete Notebook.

        Args:
            name: Notebook name
            namespace: Target namespace

        Returns:
            Deletion status
        """
        return self.custom_objects.delete_namespaced_custom_object(
            group="kubeflow.org",
            version="v1",
            namespace=namespace,
            plural="notebooks",
            name=name,
        )

    # ========== Project/Namespace Operations ==========

    async def create_project(
        self,
        name: str,
        display_name: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Create an OpenShift project (namespace).

        Args:
            name: Project name (DNS-compliant)
            display_name: Human-readable display name
            description: Project description

        Returns:
            Created namespace resource
        """
        body = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=name,
                annotations={
                    "openshift.io/display-name": display_name or name,
                    "openshift.io/description": description or "",
                },
            )
        )

        return self.core_v1.create_namespace(body=body)

    async def list_projects(self) -> list[dict]:
        """List all projects accessible by the user.

        Returns:
            List of namespace resources
        """
        result = self.core_v1.list_namespace()
        return [ns.to_dict() for ns in result.items]

    async def get_resource_quota(self, namespace: str) -> dict | None:
        """Get resource quota for namespace.

        Args:
            namespace: Target namespace

        Returns:
            ResourceQuota if exists, None otherwise
        """
        try:
            result = self.core_v1.list_namespaced_resource_quota(namespace=namespace)
            if result.items:
                return result.items[0].to_dict()
            return None
        except ApiException:
            return None

    # ========== RBAC Operations ==========

    async def add_user_to_project(
        self, username: str, namespace: str, role: str = "edit"
    ) -> dict:
        """Add user to project with specified role.

        Args:
            username: OpenShift username
            namespace: Target namespace
            role: Role to grant (view, edit, admin)

        Returns:
            Created RoleBinding
        """
        body = client.V1RoleBinding(
            metadata=client.V1ObjectMeta(
                name=f"{username}-{role}",
                namespace=namespace,
            ),
            role_ref=client.V1RoleRef(
                api_group="rbac.authorization.k8s.io",
                kind="ClusterRole",
                name=role,
            ),
            subjects=[
                client.V1Subject(
                    kind="User",
                    name=username,
                    api_group="rbac.authorization.k8s.io",
                )
            ],
        )

        return self.rbac_v1.create_namespaced_role_binding(
            namespace=namespace, body=body
        )

    # ========== Pod Operations (for logs and diagnostics) ==========

    async def get_pod_logs(
        self, name: str, namespace: str, tail_lines: int = 100
    ) -> str:
        """Get pod logs.

        Args:
            name: Pod name
            namespace: Target namespace
            tail_lines: Number of lines to retrieve

        Returns:
            Pod logs as string
        """
        return self.core_v1.read_namespaced_pod_log(
            name=name,
            namespace=namespace,
            tail_lines=tail_lines,
        )

    async def list_pods_for_inference_service(
        self, inference_service_name: str, namespace: str
    ) -> list[dict]:
        """List pods associated with an InferenceService.

        Args:
            inference_service_name: InferenceService name
            namespace: Target namespace

        Returns:
            List of pod resources
        """
        label_selector = f"serving.kserve.io/inferenceservice={inference_service_name}"
        result = self.core_v1.list_namespaced_pod(
            namespace=namespace, label_selector=label_selector
        )
        return [pod.to_dict() for pod in result.items]

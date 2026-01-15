"""OpenShift AI resource reference data models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    """OpenShift AI resource types."""

    MODEL_DEPLOYMENT = "model_deployment"  # InferenceService (alias)
    INFERENCE_SERVICE = "inference_service"  # InferenceService (canonical)
    PIPELINE = "pipeline"  # Pipeline/PipelineRun (alias)
    DATA_PIPELINE = "data_pipeline"  # Pipeline/PipelineRun (canonical)
    PIPELINE_RUNS = "pipeline_runs"  # Pipeline run history
    NOTEBOOK = "notebook"  # Notebook workbench
    PROJECT = "project"  # OpenShift Project/Namespace
    MODEL_VERSION = "model_version"  # Model Registry entry


class ResourceReference(BaseModel):
    """Pointer to OpenShift AI resource.

    Represents a reference to a Kubernetes custom resource managed by OpenShift AI.
    """

    resource_id: str
    resource_type: ResourceType
    name: str
    namespace: str
    current_state: dict | None = None
    last_updated: datetime | None = None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class InferenceServiceSpec(BaseModel):
    """KServe InferenceService specification.

    Represents the desired state for a deployed ML model.
    """

    name: str
    namespace: str
    predictor: dict  # Predictor configuration
    replicas: int = Field(default=1, ge=1, le=100)
    resources: dict | None = None  # Resource requests/limits
    metadata: dict | None = None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class NotebookSpec(BaseModel):
    """Kubeflow Notebook specification.

    Represents the desired state for a Jupyter notebook environment.
    """

    name: str
    namespace: str
    image: str  # Container image with ML libraries
    memory: str = "4Gi"  # e.g., "4Gi", "8Gi"
    cpu: str = "2"  # e.g., "2", "4"
    gpu: int = Field(default=0, ge=0)  # Number of GPUs
    volume_size: str = "10Gi"  # Persistent volume size
    metadata: dict | None = None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class PipelineSpec(BaseModel):
    """Kubeflow Pipeline specification.

    Represents the desired state for a data pipeline.
    """

    name: str
    namespace: str
    pipeline_yaml: str  # Pipeline definition in YAML
    parameters: dict = Field(default_factory=dict)
    schedule: str | None = None  # Cron schedule
    metadata: dict | None = None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ProjectSpec(BaseModel):
    """OpenShift Project specification.

    Represents the desired state for an OpenShift project/namespace.
    """

    name: str = Field(..., pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    display_name: str | None = None
    description: str | None = None
    resource_quotas: dict | None = None  # Memory, CPU limits
    limit_ranges: dict | None = None  # Min/max resource constraints
    metadata: dict | None = None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True

# OpenShift AI APIs and Python Client Libraries Research

**Research Date**: 2026-01-14
**Focus**: Programmatic control of OpenShift AI from external applications

---

## Executive Summary

Red Hat OpenShift AI does not have a single unified Python SDK. Instead, it exposes APIs through Kubernetes Custom Resources (CRDs) and integrates multiple specialized Python client libraries from the Kubeflow ecosystem. Programmatic control is achieved primarily through:

1. **Kubernetes Python client** (`kubernetes-client/python`) for core resource management
2. **OpenShift Python clients** for OpenShift-specific features
3. **KServe SDK** for model serving operations
4. **Kubeflow Pipelines SDK** for pipeline orchestration
5. **Model Registry client** for model lifecycle management

Authentication follows standard OpenShift patterns using OAuth tokens or service accounts.

---

## 1. Python Client Libraries

### 1.1 Core Kubernetes/OpenShift Clients

#### openshift-restclient-python
- **Package**: `openshift` on PyPI
- **Repository**: https://github.com/openshift/openshift-restclient-python
- **Purpose**: Python client for Kubernetes and OpenShift APIs
- **Installation**: `pip install openshift`
- **Key Features**:
  - Depends on and extends the Kubernetes Python client
  - Kubernetes client is automatically installed as dependency
  - Direct API access to all OpenShift and Kubernetes resources
  - Standard REST client pattern

#### openshift-client-python
- **Repository**: https://github.com/openshift/openshift-client-python
- **Purpose**: Alternative client using CLI (oc) tool under the hood
- **Key Features**:
  - Fluent API for rich interactions with OpenShift cluster
  - Exclusively uses command line tool (oc) for interactions
  - Readable and concise API design

#### openshift-python-wrapper
- **Package**: `openshift-python-wrapper` on PyPI
- **Release Date**: September 29, 2025
- **Purpose**: Wrapper around kubernetes-client/python with RedHat Container Virtualization support
- **Installation**: `pip install openshift-python-wrapper`

**Recommendation**: Use `openshift-restclient-python` (PyPI package: `openshift`) as the primary client for OpenShift AI resource management.

### 1.2 KServe Python SDK

- **Package**: `kserve` on PyPI
- **Documentation**: https://pypi.org/project/kserve/
- **Repository**: https://github.com/kserve/kserve
- **Purpose**: Model serving platform integration

**Two Main Components**:

1. **Client Libraries**:
   - Interact with KServe control plane APIs
   - Operations: creating, patching, deleting InferenceService instances
   - Remote cluster management

2. **Server Libraries**:
   - Implement standardized data plane APIs
   - Extended by frameworks: Scikit Learn, XGBoost, PyTorch
   - Encapsulates storage retrieval for models

**Key Features**:
- Standardized inference platform for Kubernetes
- Multi-framework support (Scikit-learn, XGBoost, PyTorch, TensorFlow, ONNX)
- Storage backend support: S3, GCS, Azure Blob Storage
- OpenShift AI single-model serving platform based on KServe

**Installation**:
```bash
pip install kserve
# or
uv pip install kserve
```

### 1.3 Kubeflow Pipelines SDK

- **Package**: `kfp` on PyPI
- **Purpose**: Pipeline orchestration and automation

**Version Information** (Critical):

| OpenShift AI Version | Pipeline Version | SDK Package | Notes |
|---------------------|------------------|-------------|-------|
| 2.5 - 2.15 | Data Science Pipelines 1.0 | `kfp-tekton==1.5.x` | Tekton backend, **DEPRECATED** |
| 2.16+ | Data Science Pipelines 2.0 | `kfp` (latest, 2.x) | Argo Workflow backend |

**Important Migration Notes**:
- **Data Science Pipelines 1.0** (deprecated as of v2.16):
  - Used kfp-tekton SDK version 1.5.x
  - Compiled to Tekton-formatted YAML
  - No longer supported in OpenShift AI 2.16+

- **Data Science Pipelines 2.0** (current):
  - Uses standard `kfp` library (latest version)
  - Argo Workflow backend (not Tekton)
  - Compiles to Intermediate Representation (IR) YAML
  - **Resources from DSP 1.0 cannot be viewed or managed in DSP 2.0**

**Key Features**:
- Define end-to-end ML/data pipelines in Python
- Component-based architecture
- Pipeline compilation to YAML
- Integration with OpenShift AI pipeline servers
- OAuth-protected pipeline server routes

**Basic Usage**:
```python
from kfp import dsl, compiler

@dsl.pipeline(name="my-pipeline")
def my_pipeline():
    # Define pipeline steps
    pass

# Compile to IR YAML
compiler.Compiler().compile(my_pipeline, "pipeline.yaml")
```

**Client Authentication**:
```python
import kfp

# Pipeline server protected by OpenShift OAuth
# Requires valid access token
client = kfp.Client(
    host="https://pipeline-server-route",
    existing_token="<oauth-token>"
)
```

### 1.4 Model Registry Python Client

- **Package**: `model-registry` on PyPI
- **Documentation**: https://pypi.org/project/model-registry/
- **Purpose**: Model lifecycle management and metadata tracking

**Key Features**:
- High-level interface for model registry server
- Part of Kubeflow ecosystem (alpha status)
- Python 3.10+ required
- Apache-2.0 license
- Optional Hugging Face integration

**Installation**:
```bash
pip install model-registry

# With optional dependencies (e.g., Hugging Face)
pip install model-registry[huggingface]
```

**Basic Usage**:
```python
from model_registry import ModelRegistry

# Connect to registry server
registry = ModelRegistry(
    "https://registry-server-address",
    author="Your Name"
)

# Register models, upload artifacts, etc.
```

**OCI Storage Support**:
- Requires `skopeo` or `oras` CLI tools
- OCI-based artifact storage
- Model versioning and metadata

---

## 2. OpenShift AI API Structure

### 2.1 Custom Resource Definitions (CRDs)

OpenShift AI extends Kubernetes with several custom resources. All CRDs are managed through the Kubernetes API server.

#### Core Platform CRDs

| Resource | API Version | Kind | Purpose |
|----------|-------------|------|---------|
| Data Science Cluster | `datasciencecluster.opendatahub.io/v1` | DataScienceCluster | Component management |
| DSC Initialization | `dscinitialization.opendatahub.io/v1` | DSCInitialization | Platform initialization |
| Notebook | `kubeflow.org/v1` | Notebook | Workbench/notebook management |
| InferenceService | `serving.kserve.io/v1beta1` | InferenceService | Model serving (single-model) |
| ServingRuntime | `serving.kserve.io/v1alpha1` | ServingRuntime | Model server configuration |
| ModelRegistry | Custom (operator-managed) | ModelRegistry | Model registry instance |

#### DataScienceCluster Resource

**Purpose**: Configure which OpenShift AI components are installed and managed

**Example**:
```yaml
apiVersion: datasciencecluster.opendatahub.io/v1
kind: DataScienceCluster
metadata:
  name: default-dsc
spec:
  components:
    codeflare:
      managementState: Removed
    dashboard:
      managementState: Managed
    datasciencepipelines:
      managementState: Managed
    kserve:
      managementState: Managed
    kueue:
      managementState: Managed
    modelmeshserving:
      managementState: Managed
    ray:
      managementState: Managed
    workbenches:
      managementState: Managed
```

**Management States**:
- `Managed`: OpenShift AI Operator manages the component
- `Removed`: Component not installed/managed

#### DSCInitialization Resource

**Purpose**: Configure platform-wide settings (service mesh, monitoring, certificates)

**API Version**: `dscinitialization.opendatahub.io/v1`

**Key Spec Fields**:
```yaml
apiVersion: dscinitialization.opendatahub.io/v1
kind: DSCInitialization
metadata:
  name: default-dsci
spec:
  applicationsNamespace: redhat-ods-applications

  serviceMesh:
    managementState: Managed
    controlPlane:
      name: data-science-smcp
      namespace: istio-system
      metricsCollection: Istio

  monitoring:
    managementState: Managed
    namespace: redhat-ods-monitoring
    metrics:
      replicas: 2
      resources:
        limits:
          cpu: "1"
          memory: 2Gi
      storage:
        size: 10Gi
    traces:
      storageBackend: tempo
      retention: 7d

  trustedCABundle:
    managementState: Managed
    customCABundle: |
      -----BEGIN CERTIFICATE-----
      ...
      -----END CERTIFICATE-----

  devFlags:
    logLevel: info  # or: debug, warn, error
    logMode: production  # or: development
```

#### Notebook Resource

**Purpose**: Create and manage workbenches (Jupyter notebook environments)

**API Version**: `kubeflow.org/v1` (stable)

**Example**:
```yaml
apiVersion: kubeflow.org/v1
kind: Notebook
metadata:
  name: my-workbench
  namespace: my-data-science-project
  annotations:
    notebooks.opendatahub.io/inject-oauth: 'true'
    opendatahub.io/image-display-name: 'Standard Data Science'
    openshift.io/display-name: 'My Workbench'
    opendatahub.io/username: 'data-scientist'
spec:
  template:
    spec:
      containers:
      - name: notebook
        image: image-registry.openshift-image-registry.svc:5000/redhat-ods-applications/s2i-generic-data-science-notebook:2023.2
        env:
        - name: JUPYTER_IMAGE
          value: 'image-registry.openshift-image-registry.svc:5000/...'
        resources:
          limits:
            cpu: '2'
            memory: 8Gi
          requests:
            cpu: '1'
            memory: 4Gi
        volumeMounts:
        - name: workspace
          mountPath: /opt/app-root/src
      volumes:
      - name: workspace
        persistentVolumeClaim:
          claimName: my-workbench-pvc
```

**Workbench Control**:
- **Stop notebook**: Add annotation `kubeflow-resource-stopped: '<timestamp>'`
- **Start notebook**: Remove the stopped annotation

#### InferenceService Resource (KServe)

**Purpose**: Deploy models on single-model serving platform

**API Version**: `serving.kserve.io/v1beta1`

**Example**:
```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: my-model
  namespace: my-data-science-project
  annotations:
    serving.kserve.io/deploymentMode: Serverless
    serving.knative.openshift.io/enablePassthrough: 'true'
spec:
  predictor:
    model:
      modelFormat:
        name: onnx
      runtime: kserve-ovms
      storageUri: s3://my-bucket/models/my-model
      resources:
        limits:
          cpu: '2'
          memory: 8Gi
        requests:
          cpu: '1'
          memory: 4Gi
```

**Serving Platforms**:
- **Single-model serving**: KServe-based, each model on dedicated server
- **Multi-model serving**: ModelMesh-based, multiple models share server

### 2.2 API Endpoints

#### Model Inference API
After deploying a model via InferenceService:
- **Endpoint**: Automatically created inference endpoint
- **Access**: Via inference endpoint URL (OAuth-protected)
- **Protocol**: REST API (KServe V2 protocol)
- **Format**: JSON input/output

**Example Inference Request**:
```python
import requests

response = requests.post(
    "https://my-model-predictor-my-project.apps.cluster.example.com/v2/models/my-model/infer",
    headers={
        "Authorization": f"Bearer {oauth_token}",
        "Content-Type": "application/json"
    },
    json={
        "inputs": [
            {
                "name": "input-0",
                "shape": [1, 10],
                "datatype": "FP32",
                "data": [0.1, 0.2, ...]
            }
        ]
    }
)
predictions = response.json()
```

#### Pipeline API
- **Access**: Via pipeline server route (OAuth-protected)
- **Client**: Kubeflow Pipelines client
- **Operations**:
  - Upload pipelines
  - Create pipeline runs
  - Manage pipeline versions
  - Query run status and artifacts

#### Dashboard Configuration API
- **Resource**: OdhDashboardConfig custom resource
- **Access**: Via Kubernetes API (administrator perspective)
- **Purpose**: Configure dashboard settings, notebook images, accelerators

---

## 3. Authentication Methods

### 3.1 OAuth Tokens

**Primary Method**: OpenShift OAuth server distributes access tokens for API authentication.

**Token Acquisition**:
```bash
# Using oc CLI
oc whoami --show-token

# Output: sha256~abc123...
```

**Usage in Python**:
```python
from kubernetes import client, config
import os

# Set token
token = os.environ['OPENSHIFT_TOKEN']
configuration = client.Configuration()
configuration.host = "https://api.cluster.example.com:6443"
configuration.api_key = {"authorization": f"Bearer {token}"}
configuration.verify_ssl = True

api_client = client.ApiClient(configuration)
```

### 3.2 Service Accounts

**Purpose**: Allow components to access API without user credentials

**Service Account as OAuth Client**:
- Service accounts can act as constrained OAuth clients
- Request limited scopes for basic user info and namespace-level permissions

**Configuration**:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pipeline-runner
  namespace: my-data-science-project
  annotations:
    # OAuth redirect URI
    serviceaccounts.openshift.io/oauth-redirecturi.first: "https://pipeline-server/callback"
    # Enable WWW-Authenticate challenges
    serviceaccounts.openshift.io/oauth-want-challenges: "true"
```

**OAuth Client Parameters**:
- **Client ID**: `system:serviceaccount:<namespace>:<service-account-name>`
- **Client Secret**: Any API token for that service account

**Token Retrieval**:
```bash
# Get service account token
oc sa get-token pipeline-runner -n my-data-science-project
```

**Usage in Python**:
```python
from kubernetes import client, config

# Load in-cluster config (when running in a pod)
config.load_incluster_config()

# Or use service account token explicitly
token = open('/var/run/secrets/kubernetes.io/serviceaccount/token').read()
configuration = client.Configuration()
configuration.host = "https://kubernetes.default.svc"
configuration.api_key = {"authorization": f"Bearer {token}"}
configuration.ssl_ca_cert = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
```

### 3.3 OAuth Proxy Integration

**Repository**: https://github.com/openshift/oauth-proxy

**Purpose**: Reverse proxy providing authentication via OAuth and service accounts

**Use Cases**:
- Protect application endpoints with OpenShift authentication
- Integrate external services with OpenShift auth
- Pipeline server, dashboard, and other OpenShift AI components use this pattern

---

## 4. API Versions and Stability

### 4.1 Stable APIs (v1)

| API Group | Resource | Version | Stability |
|-----------|----------|---------|-----------|
| kubeflow.org | Notebook | v1 | **Stable** |
| datasciencecluster.opendatahub.io | DataScienceCluster | v1 | **Stable** |
| dscinitialization.opendatahub.io | DSCInitialization | v1 | **Stable** |

### 4.2 Beta APIs (v1beta1)

| API Group | Resource | Version | Stability |
|-----------|----------|---------|-----------|
| serving.kserve.io | InferenceService | v1beta1 | **Beta** - Stable interface, may have minor changes |
| serving.kserve.io | ServingRuntime | v1beta1 | **Beta** |

### 4.3 Alpha APIs (v1alpha1)

| API Group | Resource | Version | Stability |
|-----------|----------|---------|-----------|
| serving.kserve.io | ServingRuntime | v1alpha1 | **Alpha** - May change significantly |
| Various | Pipeline components | v1alpha1 | **Alpha** |

### 4.4 Recommended API Versions

**For Production Use**:
- ✅ Notebook: `kubeflow.org/v1`
- ✅ DataScienceCluster: `datasciencecluster.opendatahub.io/v1`
- ✅ DSCInitialization: `dscinitialization.opendatahub.io/v1`
- ⚠️ InferenceService: `serving.kserve.io/v1beta1` (beta, but recommended)

**Avoid for Production**:
- ❌ Any v1alpha1 APIs (unless necessary and understanding stability implications)

---

## 5. Programmatic Control Examples

### 5.1 Managing Notebooks with Python

```python
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml

# Load kube config
config.load_kube_config()

# Create custom objects API client
api = client.CustomObjectsApi()

# Define notebook
notebook = {
    "apiVersion": "kubeflow.org/v1",
    "kind": "Notebook",
    "metadata": {
        "name": "data-science-workbench",
        "namespace": "my-project",
        "annotations": {
            "notebooks.opendatahub.io/inject-oauth": "true",
            "opendatahub.io/image-display-name": "Standard Data Science"
        }
    },
    "spec": {
        "template": {
            "spec": {
                "containers": [{
                    "name": "notebook",
                    "image": "image-registry.openshift-image-registry.svc:5000/redhat-ods-applications/s2i-generic-data-science-notebook:2023.2",
                    "resources": {
                        "limits": {"cpu": "2", "memory": "8Gi"},
                        "requests": {"cpu": "1", "memory": "4Gi"}
                    }
                }]
            }
        }
    }
}

# Create notebook
try:
    api.create_namespaced_custom_object(
        group="kubeflow.org",
        version="v1",
        namespace="my-project",
        plural="notebooks",
        body=notebook
    )
    print("Notebook created successfully")
except ApiException as e:
    print(f"Error creating notebook: {e}")

# List notebooks in namespace
notebooks = api.list_namespaced_custom_object(
    group="kubeflow.org",
    version="v1",
    namespace="my-project",
    plural="notebooks"
)

for nb in notebooks['items']:
    print(f"Notebook: {nb['metadata']['name']}")

# Stop notebook (add stopped annotation)
from datetime import datetime
patch = {
    "metadata": {
        "annotations": {
            "kubeflow-resource-stopped": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        }
    }
}

api.patch_namespaced_custom_object(
    group="kubeflow.org",
    version="v1",
    namespace="my-project",
    plural="notebooks",
    name="data-science-workbench",
    body=patch
)
```

### 5.2 Deploying Models with KServe SDK

```python
from kubernetes import client, config
from kserve import KServeClient, V1beta1InferenceService, V1beta1InferenceServiceSpec
from kserve import V1beta1PredictorSpec, V1beta1SKLearnSpec

# Load kube config
config.load_kube_config()

# Create KServe client
kserve_client = KServeClient()

# Define InferenceService
isvc = V1beta1InferenceService(
    api_version="serving.kserve.io/v1beta1",
    kind="InferenceService",
    metadata=client.V1ObjectMeta(
        name="sklearn-iris",
        namespace="my-project"
    ),
    spec=V1beta1InferenceServiceSpec(
        predictor=V1beta1PredictorSpec(
            sklearn=V1beta1SKLearnSpec(
                storage_uri="s3://my-bucket/models/sklearn/iris",
                resources=client.V1ResourceRequirements(
                    requests={"cpu": "100m", "memory": "1Gi"},
                    limits={"cpu": "1", "memory": "2Gi"}
                )
            )
        )
    )
)

# Create InferenceService
kserve_client.create(isvc)

# Get InferenceService status
kserve_client.get("sklearn-iris", namespace="my-project")

# Delete InferenceService
kserve_client.delete("sklearn-iris", namespace="my-project")
```

### 5.3 Managing Pipelines

```python
import kfp
from kfp import dsl, compiler

# Connect to pipeline server (requires OAuth token)
client = kfp.Client(
    host="https://ds-pipeline-dspa.my-project.svc.cluster.local:8443",
    existing_token="<oauth-token>"
)

# Define a simple pipeline
@dsl.pipeline(name="training-pipeline")
def training_pipeline(learning_rate: float = 0.01):
    # Define pipeline steps using kfp.dsl.ContainerOp or components
    pass

# Compile pipeline
compiler.Compiler().compile(training_pipeline, "pipeline.yaml")

# Upload pipeline
client.upload_pipeline(
    pipeline_package_path="pipeline.yaml",
    pipeline_name="training-pipeline",
    description="Model training pipeline"
)

# Create pipeline run
run = client.create_run_from_pipeline_func(
    training_pipeline,
    arguments={"learning_rate": 0.001},
    experiment_name="model-experiments"
)

# Monitor run
run_detail = client.wait_for_run_completion(run.run_id, timeout=3600)
print(f"Run status: {run_detail.run.status}")
```

### 5.4 Model Registry Operations

```python
from model_registry import ModelRegistry

# Connect to model registry
registry = ModelRegistry(
    "https://model-registry-my-project.apps.cluster.example.com",
    author="Data Science Team"
)

# Register a model version
model_version = registry.register_model(
    model_name="fraud-detection",
    version="1.0.0",
    model_uri="s3://my-bucket/models/fraud-detection/v1",
    description="Initial production model",
    metadata={
        "framework": "scikit-learn",
        "accuracy": 0.95,
        "precision": 0.93
    }
)

# Query registered models
models = registry.list_models()
for model in models:
    print(f"Model: {model.name}, Latest version: {model.latest_version}")

# Get specific model version
version = registry.get_model_version("fraud-detection", "1.0.0")
print(f"Model URI: {version.model_uri}")
print(f"Metadata: {version.metadata}")
```

### 5.5 Component Management

```python
from kubernetes import client, config

config.load_kube_config()
api = client.CustomObjectsApi()

# Get DataScienceCluster
dsc = api.get_cluster_custom_object(
    group="datasciencecluster.opendatahub.io",
    version="v1",
    plural="datascienceclusters",
    name="default-dsc"
)

print(f"Current components: {dsc['spec']['components']}")

# Update component management state
patch = {
    "spec": {
        "components": {
            "kserve": {"managementState": "Managed"},
            "datasciencepipelines": {"managementState": "Managed"},
            "workbenches": {"managementState": "Managed"}
        }
    }
}

api.patch_cluster_custom_object(
    group="datasciencecluster.opendatahub.io",
    version="v1",
    plural="datascienceclusters",
    name="default-dsc",
    body=patch
)
```

---

## 6. Summary and Recommendations

### 6.1 Python SDK Strategy

**For External Application Control of OpenShift AI**:

1. **Install Core Libraries**:
   ```bash
   pip install openshift  # OpenShift REST client
   pip install kserve     # Model serving
   pip install kfp        # Pipelines (v2.x for OpenShift AI 2.16+)
   pip install model-registry  # Model registry
   ```

2. **Authentication**:
   - Use service accounts for automated processes
   - Use OAuth tokens for user-driven operations
   - Store tokens securely (environment variables, secrets)

3. **API Version Selection**:
   - Prefer v1 stable APIs (Notebook, DataScienceCluster, DSCInitialization)
   - Use v1beta1 KServe APIs (recommended for production)
   - Avoid v1alpha1 APIs unless necessary

4. **Resource Management Pattern**:
   ```python
   from kubernetes import client, config

   # Load configuration
   config.load_kube_config()  # or load_incluster_config()

   # Create API client
   api = client.CustomObjectsApi()

   # CRUD operations on custom resources
   # - create_namespaced_custom_object()
   # - get_namespaced_custom_object()
   # - patch_namespaced_custom_object()
   # - delete_namespaced_custom_object()
   # - list_namespaced_custom_object()
   ```

### 6.2 Key API Resources for External Control

| Operation | API Resource | Python Client | API Version |
|-----------|--------------|---------------|-------------|
| Notebook Management | Notebook | kubernetes.client | kubeflow.org/v1 |
| Model Deployment | InferenceService | kserve.KServeClient | serving.kserve.io/v1beta1 |
| Pipeline Execution | Pipeline runs | kfp.Client | Kubeflow API |
| Model Registry | Model versions | model_registry.ModelRegistry | Registry API |
| Component Config | DataScienceCluster | kubernetes.client | datasciencecluster.opendatahub.io/v1 |
| Platform Config | DSCInitialization | kubernetes.client | dscinitialization.opendatahub.io/v1 |

### 6.3 Authentication Recommendations

**For External Applications**:
- Create dedicated service account in target namespace
- Grant necessary RBAC permissions (edit/admin role)
- Retrieve service account token
- Use token for API authentication

**Example Service Account Setup**:
```bash
# Create service account
oc create sa openshift-ai-controller -n my-project

# Grant permissions
oc policy add-role-to-user admin system:serviceaccount:my-project:openshift-ai-controller -n my-project

# Get token
oc sa get-token openshift-ai-controller -n my-project
```

### 6.4 API Stability Considerations

✅ **Production-Ready**:
- Notebook API (kubeflow.org/v1)
- DataScienceCluster API (v1)
- DSCInitialization API (v1)
- KServe InferenceService (v1beta1) - Beta but stable interface

⚠️ **Use with Caution**:
- Alpha APIs (v1alpha1) - Subject to breaking changes
- Pipeline APIs - Recent migration from DSP 1.0 to 2.0

📝 **Version Compatibility**:
- OpenShift AI 2.16+ requires KFP 2.x (not kfp-tekton)
- Check OpenShift AI version before choosing pipeline SDK

---

## 7. References and Documentation

### Official Documentation
- [Red Hat OpenShift AI Cloud Service Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_cloud_service/1)
- [Red Hat OpenShift AI Self-Managed Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [OpenShift Container Platform REST API](https://docs.openshift.com/container-platform/4.16/rest_api/index.html)
- [Kubeflow Notebooks](https://www.kubeflow.org/docs/components/notebooks/quickstart-guide/)
- [KServe Documentation](https://kserve.github.io/website/)
- [Kubeflow Pipelines SDK](https://kubeflow-pipelines.readthedocs.io/)

### GitHub Repositories
- [OpenShift REST Client Python](https://github.com/openshift/openshift-restclient-python)
- [OpenShift Client Python](https://github.com/openshift/openshift-client-python)
- [KServe](https://github.com/kserve/kserve)
- [OpenDataHub Operator](https://github.com/opendatahub-io/opendatahub-operator)
- [Model Registry Operator](https://github.com/opendatahub-io/model-registry-operator)
- [Data Science Pipelines Operator](https://github.com/opendatahub-io/data-science-pipelines-operator)
- [OAuth Proxy](https://github.com/openshift/oauth-proxy)

### Python Packages
- [openshift (PyPI)](https://pypi.org/project/openshift/)
- [openshift-python-wrapper (PyPI)](https://pypi.org/project/openshift-python-wrapper/)
- [kserve (PyPI)](https://pypi.org/project/kserve/)
- [model-registry (PyPI)](https://pypi.org/project/model-registry/)
- [kfp (PyPI)](https://pypi.org/project/kfp/)

### Community Resources
- [AI on OpenShift](https://ai-on-openshift.io/)
- [Red Hat Developer - OpenShift AI](https://developers.redhat.com/products/red-hat-openshift-ai)
- [OpenDataHub](https://opendatahub.io/)

### Key Articles
- [From raw data to model serving with OpenShift AI](https://developers.redhat.com/articles/2025/07/29/raw-data-model-serving-openshift-ai)
- [Deploy an LLM inference service on OpenShift AI](https://developers.redhat.com/articles/2025/11/03/deploy-llm-inference-service-openshift-ai)
- [What's new with data science pipelines in Red Hat OpenShift AI](https://www.redhat.com/en/blog/whats-new-data-science-pipelines-red-hat-openshift-ai)
- [Implementing MLOps with Kubeflow Pipelines](https://developers.redhat.com/articles/2024/01/25/implement-mlops-kubeflow-pipelines)

---

## Appendix A: API Version Matrix

| Component | API Group | Current Version | Stability | Notes |
|-----------|-----------|-----------------|-----------|-------|
| Notebook | kubeflow.org | v1 | Stable | Workbench management |
| DataScienceCluster | datasciencecluster.opendatahub.io | v1 | Stable | Component configuration |
| DSCInitialization | dscinitialization.opendatahub.io | v1 | Stable | Platform initialization |
| InferenceService | serving.kserve.io | v1beta1 | Beta | Model serving |
| ServingRuntime | serving.kserve.io | v1alpha1, v1beta1 | Alpha/Beta | Model server runtime |
| Pipeline | kubeflow.org | v1beta1 | Beta | Pipeline definitions (DSP 2.0) |
| PipelineRun | tekton.dev | v1beta1 | Deprecated | Removed in DSP 2.0 |

## Appendix B: Authentication Flow Diagram

```
External Application
        |
        | (1) Get OAuth Token or SA Token
        v
OAuth Server / Service Account
        |
        | (2) Token
        v
External Application
        |
        | (3) API Request with Bearer Token
        v
OpenShift API Server
        |
        | (4) Token Validation
        v
Kubernetes RBAC
        |
        | (5) Permission Check
        v
Custom Resource Operation
        |
        | (6) Response
        v
External Application
```

## Appendix C: Component Interaction Map

```
External Application
        |
        +-- Kubernetes Client -----> Notebook CR -----> Workbench Pods
        |
        +-- KServe Client ---------> InferenceService --> Model Server Pods
        |
        +-- KFP Client ------------> Pipeline Server --> Argo Workflows
        |
        +-- Model Registry Client -> ModelRegistry ---> Registry Service
        |
        +-- Kubernetes Client -----> DataScienceCluster -> Component Operators
```

---

**Research Completed**: 2026-01-14
**Researcher**: Claude (Anthropic)
**Document Version**: 1.0

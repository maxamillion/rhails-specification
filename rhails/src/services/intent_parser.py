"""Intent parser service for natural language understanding.

This service parses user natural language queries into structured intents
that can be executed by operation executors using pattern matching and
parameter extraction.
"""

import re
import uuid
from typing import Any

from src.models.intent import ActionType, UserIntent
from src.models.openshift import ResourceType


class IntentParser:
    """Parse natural language queries into structured user intents."""

    def __init__(self):
        """Initialize intent parser with pattern matchers."""
        # No LLM client needed - using pattern-based parsing

        # Action type patterns for quick classification
        # Ordered from most specific to least specific to avoid false matches
        # Pipeline patterns MUST come before model patterns since "create" is ambiguous
        self.action_patterns = {
            # Pipeline creation patterns (before model deployment to avoid conflicts)
            ActionType.CREATE_PIPELINE: [
                r"\bcreate\b.*\bpipeline\b",
                r"\bset\s+up\b.*\bpipeline\b",
                r"\bbuild\b.*\bpipeline\b",
                r"\bpipeline\b.*\bto\b.*\b(?:preprocess|transform|analyze)\b",
            ],
            # Pipeline update patterns
            ActionType.UPDATE_PIPELINE: [
                r"\bupdate\b.*\bpipeline\b",
                r"\bchange\b.*\bpipeline\b",
                r"\bmodify\b.*\bpipeline\b",
                r"\bpipeline\b.*\bschedule\b",
            ],
            # List pipelines
            ActionType.LIST_PIPELINES: [
                r"\blist\b.*\bpipelines?\b",
                r"\bshow\b.*\bpipelines?\b",
                r"\bwhat\b.*\bpipelines?\b",
                r"\ball\b.*\bpipelines?\b",
            ],
            # Notebook control patterns (more specific, must come before creation)
            ActionType.STOP_NOTEBOOK: [
                r"\bstop\b\s+(?:the|my)\s+[a-z0-9\-]+",  # "stop the ml-notebook"
                r"\bstop\b.*\bnotebook\b",
                r"\bshut\s*down\b.*\bnotebook\b",
                r"\bpause\b.*\bnotebook\b",
            ],
            ActionType.START_NOTEBOOK: [
                r"\bstart\b\s+(?:the|my)\s+[a-z0-9\-]+",  # "start my data-science-notebook"
                r"\bresume\b.*\bnotebook\b",
                r"\brestart\b.*\bnotebook\b",
            ],
            # Notebook creation patterns (less specific, comes after control)
            ActionType.CREATE_NOTEBOOK: [
                r"\bcreate\b.*\bnotebook\b",
                r"\blaunch\b.*\b(?:a|an|new)\s+notebook\b",
                r"\bstart\b.*\b(?:a|an|new)\s+notebook\b",  # Only match "start a/an/new notebook"
                r"\bnotebook\b.*\bwith\b",
            ],
            # Notebook deletion patterns
            ActionType.DELETE_NOTEBOOK: [
                r"\bdelete\b.*\bnotebook\b",
                r"\bremove\b.*\bnotebook\b",
                r"\bdrop\b.*\bnotebook\b",
            ],
            # List notebooks
            ActionType.LIST_NOTEBOOKS: [
                r"\blist\b.*\bnotebooks?\b",
                r"\bshow\b.*\bnotebooks?\b",
                r"\bwhat\b.*\bnotebooks?\b",
                r"\ball\b.*\bnotebooks?\b",
            ],
            # Project operations (before model operations to prevent conflicts)
            ActionType.GET_PROJECT_RESOURCES: [
                r"\bhow\s+much\b.*\busing\b",
                r"\bresource\s+usage\b.*\bfor\b",
                r"\bresource\s+consumption\b",
                r"\bshow\b.*\bresource.*\busage\b",
                r"\bwhat.*\busing\b",
            ],
            ActionType.ADD_USER_TO_PROJECT: [
                r"\badd\s+(?:user\s+)?[\w@.\-]+\s+to\b",
                r"\bgive\s+[\w@.\-]+\s+access\b",
                r"\badd\s+[\w@.\-]+.*\bproject\b",
                r"\bgrant\s+[\w@.\-]+\b",
            ],
            ActionType.LIST_PROJECTS: [
                r"\blist\b.*\bprojects?\b",
                r"\bshow\b.*\bprojects?\b",
                r"\bwhat\s+projects?\b",
                r"\ball\b.*\bprojects?\b",
            ],
            ActionType.CREATE_PROJECT: [
                r"\bcreate\b.*\bproject\b",
                r"\bnew\s+project\b",
                r"\blaunch\b.*\bproject\b",
            ],
            # Monitoring and troubleshooting operations (before model operations)
            ActionType.ANALYZE_LOGS: [
                r"\bwhy\b.*\bfailing\b",
                r"\bshow\b.*\blogs\b",
                r"\blogs?\b.*\bfor\b",
                r"\bwhat\s+errors\b",
                r"\berrors\b.*\bexperiencing\b",
                r"\banalyze\b.*\blogs\b",
            ],
            ActionType.COMPARE_METRICS: [
                r"\bcompare\b.*\bperformance\b",
                r"\bcompare\b.*\bmetrics\b",
                r"\bperformance\b.*\bcompare\b",
                r"\bcompare\b.*\bto\b.*\b(?:yesterday|today|week|month)\b",
                r"\bhow\s+does\b.*\bcompare\b",
                r"\bperformance\s+comparison\b",
                r"\bcomparison\b.*\bfor\b",
            ],
            ActionType.DIAGNOSE_PERFORMANCE: [
                r"\bcpu\-bound\b",
                r"\bmemory\-bound\b",
                r"\bhigh\s+latency\b",
                r"\bdiagnose\b.*\bperformance\b",
                r"\bperformance\s+issues\b",
                r"\bwhy\b.*\b(?:slow|latency)\b",
            ],
            ActionType.GET_PREDICTION_DISTRIBUTION: [
                r"\bprediction\s+distribution\b",
                r"\bdistribution\s+of\s+predictions\b",
                r"\bprediction\s+statistics\b",
                r"\bshow\b.*\bdistribution\b",
                r"\bget\b.*\bstatistics\b",
            ],
            # Model deployment patterns (most specific first)
            ActionType.DEPLOY_MODEL: [
                r"\bdeploy\b",
                r"\bcreate\b.*\b(?:model|called)\b",
                r"\blaunch\b",
                r"\bstart\b",
            ],
            # Model scaling patterns (before general queries)
            ActionType.SCALE_MODEL: [
                r"\bscale\b",
                r"\bincrease\b.*\b(?:to|replicas?|instances?)\b",
                r"\bdecrease\b",
                r"\bscale\b.*\b(?:up|down|to)\b",
            ],
            # Model deletion patterns
            ActionType.DELETE_MODEL: [
                r"\bdelete\b",
                r"\bremove\b",
                r"\bdrop\b",
                r"\bstop\b",
            ],
            # Model status query (before list to catch specific status requests)
            ActionType.GET_STATUS: [
                r"\bstatus\b",
                r"\bis\b.*\brunning\b",
                r"\bcheck\b.*\bmodel\b",
                r"\bshow\b\s+(?:me\s+)?(?:the\s+)?[a-z0-9\-]+(?:\s+model|\s+status)",
            ],
            # List models (after GET_STATUS so specific queries are handled first)
            ActionType.LIST_MODELS: [
                r"\blist\b.*\bmodels?\b",
                r"\bshow\b.*\ball\b",
                r"\bwhat\b.*\bmodels\b",  # plural only
                r"\ball\b.*\bmodels?\b",
            ],
        }

    async def parse_intent(
        self,
        user_query: str,
        conversation_context: list[dict[str, str]] | None = None,
    ) -> UserIntent:
        """Parse user query into structured intent.

        Args:
            user_query: Natural language query from user
            conversation_context: Optional conversation history for context

        Returns:
            Structured UserIntent with action type, parameters, and confidence

        Raises:
            ValueError: If query is empty or invalid
        """
        if not user_query or not user_query.strip():
            raise ValueError("Query cannot be empty")

        # Pattern matching for action classification
        action_type = self._classify_action(user_query)

        # Extract parameters from query
        parameters = self._extract_parameters(user_query, action_type)

        # Resolve resource references from context if needed
        used_context = False
        # Check if model_name is missing or is a pronoun that needs resolution
        model_name_from_params = parameters.get("model_name")
        if (not model_name_from_params or model_name_from_params in ["it", "this", "that"]) and conversation_context:
            model_name = self._resolve_from_context(conversation_context, "model")
            if model_name:
                parameters["model_name"] = model_name
                used_context = True

        # Calculate confidence based on completeness
        confidence = self._calculate_confidence(action_type, parameters, user_query, used_context)

        # Extract target resources
        target_resources = self._extract_resources(action_type, parameters)

        # Determine if confirmation is required
        requires_confirmation = self._needs_confirmation(action_type)

        return UserIntent(
            intent_id=uuid.uuid4(),
            message_id=uuid.uuid4(),  # Will be set by caller
            action_type=action_type,
            target_resources=target_resources,
            parameters=parameters,
            confidence=confidence,
            ambiguities=[],
            requires_confirmation=requires_confirmation,
        )

    def _classify_action(self, query: str) -> ActionType:
        """Pattern-based classification for action type.

        Args:
            query: User query string

        Returns:
            ActionType enum
        """
        query_lower = query.lower()

        # Check each action type's patterns
        for action_type, patterns in self.action_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    return action_type

        # Default to list if no match
        return ActionType.LIST_MODELS

    def _extract_parameters(self, query: str, action_type: ActionType) -> dict[str, Any]:
        """Extract parameters from query based on action type.

        Args:
            query: User query string
            action_type: Classified action type

        Returns:
            Dictionary of extracted parameters
        """
        parameters: dict[str, Any] = {}

        # Extract model name (for model and monitoring operations)
        if action_type in [
            ActionType.DEPLOY_MODEL,
            ActionType.SCALE_MODEL,
            ActionType.DELETE_MODEL,
            ActionType.GET_STATUS,
            ActionType.ANALYZE_LOGS,
            ActionType.COMPARE_METRICS,
            ActionType.DIAGNOSE_PERFORMANCE,
            ActionType.GET_PREDICTION_DISTRIBUTION,
        ]:
            model_name = self._extract_model_name(query)
            if model_name:
                parameters["model_name"] = model_name

        # Extract pipeline name (for pipeline operations)
        if action_type in [ActionType.CREATE_PIPELINE, ActionType.UPDATE_PIPELINE]:
            pipeline_name = self._extract_pipeline_name(query)
            if pipeline_name:
                parameters["pipeline_name"] = pipeline_name

        # Extract notebook name (for notebook operations)
        if action_type in [ActionType.CREATE_NOTEBOOK, ActionType.START_NOTEBOOK, ActionType.STOP_NOTEBOOK, ActionType.DELETE_NOTEBOOK]:
            notebook_name = self._extract_notebook_name(query)
            if notebook_name:
                parameters["notebook_name"] = notebook_name

        # Extract namespace
        namespace = self._extract_namespace(query)
        if namespace:
            parameters["namespace"] = namespace

        # Action-specific extractions
        if action_type == ActionType.CREATE_NOTEBOOK:
            # Extract memory
            memory = self._extract_memory(query)
            if memory:
                parameters["memory"] = memory

            # Extract CPU
            cpu = self._extract_cpu(query)
            if cpu:
                parameters["cpu"] = cpu

            # Extract GPU
            gpu = self._extract_gpu(query)
            if gpu is not None:
                parameters["gpu"] = gpu

            # Extract image
            image = self._extract_image(query)
            if image:
                parameters["image"] = image

        elif action_type in [ActionType.STOP_NOTEBOOK, ActionType.START_NOTEBOOK]:
            # Add action type to parameters for executor
            parameters["action"] = "stop" if action_type == ActionType.STOP_NOTEBOOK else "start"

        elif action_type == ActionType.DEPLOY_MODEL:
            # Extract replicas
            replicas = self._extract_replicas(query)
            if replicas is not None:
                parameters["replicas"] = replicas

            # Extract storage URI
            storage_uri = self._extract_storage_uri(query)
            if storage_uri:
                parameters["storage_uri"] = storage_uri

        elif action_type == ActionType.SCALE_MODEL:
            # Extract target replica count
            replicas = self._extract_replicas(query)
            if replicas is not None:
                parameters["replicas"] = replicas

        elif action_type == ActionType.UPDATE_PIPELINE:
            # Extract schedule information
            schedule = self._extract_schedule(query)
            if schedule:
                parameters["schedule"] = schedule

        # Project operations
        elif action_type == ActionType.CREATE_PROJECT:
            # Extract project name
            project_name = self._extract_project_name(query)
            if project_name:
                parameters["project_name"] = project_name

            # Extract memory limit
            memory_limit = self._extract_memory_limit(query)
            if memory_limit:
                parameters["memory_limit"] = memory_limit

            # Extract CPU limit
            cpu_limit = self._extract_cpu_limit(query)
            if cpu_limit:
                parameters["cpu_limit"] = cpu_limit

        elif action_type == ActionType.ADD_USER_TO_PROJECT:
            # Extract username
            username = self._extract_username(query)
            if username:
                parameters["username"] = username

            # Extract project name
            project_name = self._extract_project_name(query)
            if project_name:
                parameters["project_name"] = project_name

            # Extract role
            role = self._extract_role(query)
            if role:
                parameters["role"] = role

        elif action_type == ActionType.GET_PROJECT_RESOURCES:
            # Extract project name
            project_name = self._extract_project_name(query)
            if project_name:
                parameters["project_name"] = project_name

        # Monitoring operations
        elif action_type in [
            ActionType.ANALYZE_LOGS,
            ActionType.COMPARE_METRICS,
            ActionType.DIAGNOSE_PERFORMANCE,
            ActionType.GET_PREDICTION_DISTRIBUTION,
        ]:
            # Extract time range if present
            time_range = self._extract_time_range(query)
            if time_range:
                parameters["time_range"] = time_range

        return parameters

    def _extract_model_name(self, query: str) -> str | None:
        """Extract model name from query.

        Args:
            query: User query string

        Returns:
            Extracted model name or None
        """
        # Pattern: "model called X", "X model", action + model name
        # More specific patterns first to avoid false matches
        patterns = [
            r"(?:model\s+called\s+|called\s+)([a-z0-9\-]+)",
            r"(?:scale\s+(?:up|down)\s+)([a-z0-9\-]+)",  # "scale down X"
            r"(?:deploy|create|delete|remove|scale|increase|decrease)\s+(?:my\s+|the\s+)?([a-z0-9\-]+)",
            r"\bstatus\s+of\s+(?:my\s+|the\s+)?([a-z0-9\-]+)",
            # Monitoring patterns (specific to monitoring queries)
            r"(?:my|the|is|does)\s+([a-z0-9\-]+)\s+(?:failing|showing|experiencing)",
            r"(?:logs|errors)\s+(?:of\s+)?(?:for\s+)?(?:my\s+|the\s+)?([a-z0-9\-]+)",
            r"(?:does|how)\s+([a-z0-9\-]+)\s+(?:performance|metrics)",  # "How does X performance"
            r"(?:is|does)\s+(?:my\s+|the\s+)?([a-z0-9\-]+)\s+(?:cpu|memory)\-bound",
            r"(?:performance|metrics)\s+of\s+(?:my\s+|the\s+)?([a-z0-9\-]+)",  # "performance of my X"
            r"(?:of\s+)?(?:predictions|statistics)\s+for\s+(?:my\s+|the\s+)?([a-z0-9\-]+)",  # "of predictions for X"
            r"(?:comparison|compare)\s+for\s+([a-z0-9\-]+)",  # "comparison for X"
            r"(?:for|with)\s+([a-z0-9\-]+)\s+(?:over|model)",  # "for X over"
            r"(?:diagnose)\s+(?:performance\s+)?(?:issues\s+)?(?:with\s+)?(?:my\s+|the\s+)?([a-z0-9\-]+)",
            # General patterns (less specific, at the end)
            r"([a-z0-9\-]+)\s+model",
            r"([a-z0-9\-]+)\s+(?:to|in)\s+",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                name = match.group(1)
                # Filter out common words and numbers that aren't model names
                if name not in ["a", "an", "the", "my", "me", "model", "to", "with", "from", "for", "replicas", "instances", "up", "down"] and not name.isdigit():
                    return name

        return None

    def _extract_namespace(self, query: str) -> str | None:
        """Extract namespace from query.

        Args:
            query: User query string

        Returns:
            Extracted namespace or None
        """
        # Pattern: "in X namespace", "in X"
        patterns = [
            r"in\s+([a-z0-9\-]+)\s+namespace",
            r"namespace\s+([a-z0-9\-]+)",
            r"in\s+the\s+([a-z0-9\-]+)\s+(?:namespace|project|environment)",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return match.group(1)

        return None

    def _extract_replicas(self, query: str) -> int | None:
        """Extract replica count from query.

        Args:
            query: User query string

        Returns:
            Extracted replica count or None
        """
        # Text to number mapping
        text_numbers = {
            "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
            "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }

        # Pattern: "N replicas", "to N", "N instances", "text number replicas"
        patterns = [
            r"(\d+)\s+replicas?",
            r"to\s+(\d+)\s+(?:replicas?|instances?)?",
            r"(\d+)\s+instances?",
            r"with\s+(\d+)\s+replicas?",
            r"to\s+(zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+replicas?",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                value = match.group(1)
                try:
                    # Try numeric conversion first
                    return int(value)
                except ValueError:
                    # Try text number conversion
                    if value in text_numbers:
                        return text_numbers[value]

        return None

    def _extract_storage_uri(self, query: str) -> str | None:
        """Extract storage URI from query.

        Args:
            query: User query string

        Returns:
            Extracted storage URI or None
        """
        # Pattern: s3://, gs://, http://, https://
        pattern = r"((?:s3|gs|https?):\/\/[^\s]+)"
        match = re.search(pattern, query.lower())
        if match:
            return match.group(1)

        # Pattern: "from X"
        pattern = r"from\s+(s3:\/\/[^\s]+)"
        match = re.search(pattern, query.lower())
        if match:
            return match.group(1)

        return None

    def _extract_pipeline_name(self, query: str) -> str | None:
        """Extract pipeline name from query.

        Args:
            query: User query string

        Returns:
            Extracted pipeline name or None
        """
        # Pattern: "pipeline called X", "X pipeline", "create X", "pipeline X"
        patterns = [
            r"pipeline\s+called\s+([a-z0-9\-]+)",
            r"called\s+([a-z0-9\-]+)",
            r"(?:create|build|set\s+up)\s+(?:a\s+)?(?:pipeline\s+)?([a-z0-9\-]+)",
            r"([a-z0-9\-]+)\s+pipeline",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                name = match.group(1)
                # Filter out common words that aren't pipeline names
                if name not in ["a", "an", "the", "my", "pipeline", "data", "to", "for", "from"]:
                    return name

        return None

    def _extract_schedule(self, query: str) -> str | None:
        """Extract schedule information from query.

        Args:
            query: User query string

        Returns:
            Extracted schedule string or None
        """
        # Pattern: "every X hours/days", "hourly", "daily", "to run X"
        patterns = [
            r"every\s+(\d+\s+(?:hour|hours|minute|minutes|day|days))",
            r"(hourly|daily|weekly|monthly)",
            r"to\s+run\s+(every\s+[^\s]+(?:\s+[^\s]+)?)",
            r"schedule\s+(?:to\s+)?(.+?)(?:\s+to|\s+for|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return match.group(1)

        return None

    def _extract_notebook_name(self, query: str) -> str | None:
        """Extract notebook name from query.

        Args:
            query: User query string

        Returns:
            Extracted notebook name or None
        """
        # Pattern: "notebook called X", "X notebook", "create X", "notebook X"
        patterns = [
            r"notebook\s+called\s+([a-z0-9\-]+)",
            r"called\s+([a-z0-9\-]+)",
            r"(?:create|launch|start|stop|delete|remove)\s+(?:a|an|the|my)?\s*(?:notebook\s+)?([a-z0-9\-]+)",
            r"([a-z0-9\-]+)\s+notebook",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                name = match.group(1)
                # Filter out common words that aren't notebook names
                if name not in ["a", "an", "the", "my", "notebook", "python", "jupyter", "to", "for", "from", "with"]:
                    return name

        return None

    def _extract_memory(self, query: str) -> str | None:
        """Extract memory specification from query.

        Args:
            query: User query string

        Returns:
            Extracted memory specification in Kubernetes format (e.g., "4Gi", "8Gi")
        """
        # Pattern: "4GB", "8 GB", "16G", "2Gi", "4096Mi", "4GB RAM", "with 8GB"
        patterns = [
            r"(\d+)\s*(?:gb|g)\s+(?:of\s+)?(?:ram|memory)",  # "4GB RAM", "8G memory"
            r"(?:with|using)\s+(\d+)\s*(?:gb|g|gi|mi)",  # "with 4GB", "using 8Gi"
            r"(\d+)\s*(?:gb|g|gi|mi)(?:\s+(?:ram|memory))?",  # "4GB", "8Gi", "4096Mi"
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                value = int(match.group(1))

                # Convert to Kubernetes memory format
                # Check if the query specified Mi (mebibytes)
                if "mi" in query.lower():
                    return f"{value}Mi"
                # Default to Gi (gibibytes) for GB/G specifications
                else:
                    return f"{value}Gi"

        return None

    def _extract_cpu(self, query: str) -> str | None:
        """Extract CPU specification from query.

        Args:
            query: User query string

        Returns:
            Extracted CPU specification (e.g., "2", "4")
        """
        # Pattern: "2 CPUs", "4 cores", "with 2 CPU", "2-core"
        patterns = [
            r"(\d+)\s*(?:cpu|cpus|core|cores)",  # "2 CPUs", "4 cores"
            r"(\d+)\s*-\s*core",  # "2-core"
            r"(?:with|using)\s+(\d+)\s+(?:cpu|core)",  # "with 2 CPU"
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return match.group(1)

        return None

    def _extract_gpu(self, query: str) -> int | None:
        """Extract GPU specification from query.

        Args:
            query: User query string

        Returns:
            Extracted GPU count (e.g., 0, 1, 2) or None if not specified
        """
        # Pattern: "with GPU", "GPU support", "2 GPUs", "no GPU"

        # Check for explicit GPU count
        patterns = [
            r"(\d+)\s*(?:gpu|gpus)",  # "2 GPUs"
            r"(?:with|using)\s+(\d+)\s+gpu",  # "with 1 GPU"
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return int(match.group(1))

        # Check for generic GPU support request
        if re.search(r"\bgpu\s+support\b|\bwith\s+gpu\b|\bgpu\s+enabled\b", query.lower()):
            return 1  # Default to 1 GPU when GPU support is requested

        # Check for explicit "no GPU"
        if re.search(r"\bno\s+gpu\b|\bwithout\s+gpu\b", query.lower()):
            return 0

        return None

    def _extract_image(self, query: str) -> str | None:
        """Extract container image specification from query.

        Args:
            query: User query string

        Returns:
            Extracted container image name or common framework mapping
        """
        # Map common framework names to container images
        framework_images = {
            "tensorflow": "tensorflow/tensorflow:latest-jupyter",
            "pytorch": "pytorch/pytorch:latest",
            "python": "jupyter/scipy-notebook:latest",
            "datascience": "jupyter/datascience-notebook:latest",
            "r": "jupyter/r-notebook:latest",
            "julia": "jupyter/julia-notebook:latest",
        }

        query_lower = query.lower()

        # Check for framework keywords
        for framework, image in framework_images.items():
            if framework in query_lower:
                return image

        # Check for explicit image URIs
        # Pattern: registry/image:tag or image:tag
        pattern = r"(?:image\s+)?([a-z0-9\-\.]+/[a-z0-9\-\.]+:[a-z0-9\-\.]+)"
        match = re.search(pattern, query_lower)
        if match:
            return match.group(1)

        return None

    def _extract_project_name(self, query: str) -> str | None:
        """Extract project name from query.

        Args:
            query: User query string

        Returns:
            Extracted project name or None
        """
        # Pattern: "project called X", "project X", "for X project", "of X", "X project"
        patterns = [
            r"project\s+called\s+([a-z0-9\-]+)",
            r"project\s+named\s+([a-z0-9\-]+)",
            r"called\s+([a-z0-9\-]+)",
            r"named\s+([a-z0-9\-]+)",
            r"(?:to|for|of)\s+(?:the\s+)?([a-z0-9\-]+)(?:\s+project)?",
            r"([a-z0-9\-]+)\s+(?:project|using|access)",
            r"(?:create|for)\s+(?:the\s+)?([a-z0-9\-]+)(?:\s+(?:team|project))?",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                name = match.group(1)
                # Filter out common words that aren't project names
                if name not in ["a", "an", "the", "my", "project", "team", "to", "for", "from", "with", "access", "user"]:
                    return name

        return None

    def _extract_username(self, query: str) -> str | None:
        """Extract username from query.

        Args:
            query: User query string

        Returns:
            Extracted username or None
        """
        # Pattern: email addresses, usernames
        patterns = [
            r"(?:add|give|grant)\s+(?:user\s+)?([\w@.\-]+)",
            r"user\s+([\w@.\-]+)",
            r"([\w]+@[\w]+\.[\w]+)",  # email pattern
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                username = match.group(1)
                # Filter out common words
                if username not in ["access", "to", "permissions", "user"]:
                    return username

        return None

    def _extract_memory_limit(self, query: str) -> str | None:
        """Extract memory limit from query.

        Args:
            query: User query string

        Returns:
            Extracted memory limit in Kubernetes format (e.g., "32Gi", "64Gi")
        """
        # Pattern: "32GB", "64 GB", "128G", "limit"
        patterns = [
            r"(\d+)\s*(?:gb|g)\s+(?:of\s+)?(?:memory|ram)(?:\s+limit)?",
            r"(?:with|limit)\s+(\d+)\s*(?:gb|g|gi)",
            r"(\d+)\s*(?:gb|g|gi)(?:\s+(?:memory|ram))?\s+(?:limit|quota)?",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                value = int(match.group(1))
                # Convert to Kubernetes format (Gi)
                return f"{value}Gi"

        return None

    def _extract_cpu_limit(self, query: str) -> str | None:
        """Extract CPU limit from query.

        Args:
            query: User query string

        Returns:
            Extracted CPU limit as string (e.g., "4", "16")
        """
        # Pattern: "4 CPU", "16 cores", "CPU limit"
        patterns = [
            r"(\d+)\s*(?:cpu|cpus|core|cores)(?:\s+limit)?",
            r"(?:and|with)\s+(\d+)\s*(?:cpu|core)",
            r"cpu\s+(?:limit|quota)\s+(?:of\s+)?(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return match.group(1)

        return None

    def _extract_role(self, query: str) -> str | None:
        """Extract role/permission level from query.

        Args:
            query: User query string

        Returns:
            Extracted role (e.g., "edit", "view", "admin")
        """
        # Pattern: "with edit permissions", "as admin", "view access"
        role_mapping = {
            "edit": ["edit", "write", "contributor"],
            "view": ["view", "read", "viewer", "readonly"],
            "admin": ["admin", "administrator", "owner"],
        }

        query_lower = query.lower()

        for role, keywords in role_mapping.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return role

        return None

    def _extract_time_range(self, query: str) -> str | None:
        """Extract time range from query for monitoring operations.

        Args:
            query: User query string

        Returns:
            Extracted time range (e.g., "last week", "yesterday", "last month")
        """
        # Pattern: "last week", "yesterday", "over the last month", "past week"
        patterns = [
            r"(last\s+week)",
            r"(last\s+month)",
            r"(yesterday)",
            r"(today)",
            r"(past\s+week)",
            r"(past\s+month)",
            r"(last\s+\d+\s+(?:days?|weeks?|months?))",
            r"(?:over|for)\s+the\s+(last\s+(?:week|month|day))",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return match.group(1)

        return None

    def _calculate_confidence(
        self, action_type: ActionType, parameters: dict[str, Any], query: str, used_context: bool = False
    ) -> float:
        """Calculate confidence score for the parsed intent.

        Args:
            action_type: Classified action type
            parameters: Extracted parameters
            query: Original query
            used_context: Whether conversation context was used to resolve parameters

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # List operations don't require resource names - start with high confidence
        list_operations = {
            ActionType.LIST_MODELS,
            ActionType.LIST_PIPELINES,
            ActionType.LIST_NOTEBOOKS,
            ActionType.LIST_PROJECTS,
        }

        if action_type in list_operations:
            confidence = 0.7  # High confidence for list operations
            # Boost if namespace specified (more targeted list)
            if "namespace" in parameters:
                confidence += 0.1
        else:
            # Start with base confidence for matched action pattern
            confidence = 0.5

            # Check for resource name (model_name, pipeline_name, notebook_name, or project_name)
            has_resource_name = (
                parameters.get("model_name") or
                parameters.get("pipeline_name") or
                parameters.get("notebook_name") or
                parameters.get("project_name")
            )

            # Boost for resource name
            if "model_name" in parameters:
                confidence += 0.2
            elif "pipeline_name" in parameters:
                confidence += 0.2
            elif "notebook_name" in parameters:
                confidence += 0.2
            elif "project_name" in parameters:
                confidence += 0.2
            elif not has_resource_name:
                # No resource name - check if there's contextual information
                query_lower = query.lower()
                context_indicators = ["to", "from", "for", "with", "using", "based on"]
                has_context = any(indicator in query_lower for indicator in context_indicators)

                if has_context:
                    # Clear purpose/context even without explicit name
                    confidence = 0.5
                else:
                    # Missing name and no clear context
                    confidence = 0.3

            # Increase confidence for action-specific parameters
            if action_type == ActionType.DEPLOY_MODEL:
                if "replicas" in parameters or "storage_uri" in parameters:
                    confidence += 0.1
            elif action_type == ActionType.SCALE_MODEL:
                if "replicas" in parameters:
                    confidence += 0.2
            elif action_type == ActionType.CREATE_PIPELINE:
                # Additional confidence boost for pipeline creation with source/purpose
                if "from" in query.lower() or "source" in query.lower():
                    confidence = max(confidence, 0.5)
            elif action_type == ActionType.CREATE_NOTEBOOK:
                # Additional confidence boost for notebook creation with resource specs
                if "memory" in parameters or "cpu" in parameters or "image" in parameters:
                    confidence += 0.1
            elif action_type == ActionType.CREATE_PROJECT:
                # Additional confidence boost for project creation with resource quotas
                if "memory_limit" in parameters or "cpu_limit" in parameters:
                    confidence += 0.1
            elif action_type == ActionType.ADD_USER_TO_PROJECT:
                # Additional confidence boost for add user with username and project
                if "username" in parameters and "project_name" in parameters:
                    confidence += 0.2
                if "role" in parameters:
                    confidence += 0.1
            elif action_type == ActionType.GET_PROJECT_RESOURCES:
                # Additional confidence boost for resource query with project name
                if "project_name" in parameters:
                    confidence += 0.1

            # Boost confidence if context helped resolve ambiguity
            if used_context:
                confidence += 0.2

            # Increase confidence if namespace is specified
            if "namespace" in parameters:
                confidence += 0.1

        # Ensure confidence is within valid range
        return min(1.0, confidence)

    def _extract_resources(
        self, action_type: ActionType, parameters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract target resources from parameters.

        Args:
            action_type: The action being performed
            parameters: Parsed parameters dict

        Returns:
            List of resource references
        """
        resources = []

        # For model operations, create INFERENCE_SERVICE resource reference
        if "model_name" in parameters:
            resources.append(
                {
                    "resource_id": parameters.get("model_name", ""),
                    "type": ResourceType.INFERENCE_SERVICE,
                    "name": parameters.get("model_name", ""),
                    "namespace": parameters.get("namespace", ""),
                    "labels": parameters.get("labels", {}),
                }
            )

        # For pipeline operations, create PIPELINE resource reference
        if "pipeline_name" in parameters:
            resources.append(
                {
                    "resource_id": parameters.get("pipeline_name", ""),
                    "type": ResourceType.PIPELINE,
                    "name": parameters.get("pipeline_name", ""),
                    "namespace": parameters.get("namespace", ""),
                    "labels": parameters.get("labels", {}),
                }
            )

        # For notebook operations, create NOTEBOOK resource reference
        if "notebook_name" in parameters:
            resources.append(
                {
                    "resource_id": parameters.get("notebook_name", ""),
                    "type": ResourceType.NOTEBOOK,
                    "name": parameters.get("notebook_name", ""),
                    "namespace": parameters.get("namespace", ""),
                    "labels": parameters.get("labels", {}),
                }
            )

        # For project operations, create PROJECT resource reference
        if "project_name" in parameters:
            resources.append(
                {
                    "resource_id": parameters.get("project_name", ""),
                    "type": ResourceType.PROJECT,
                    "name": parameters.get("project_name", ""),
                    "namespace": parameters.get("namespace", ""),
                    "labels": parameters.get("labels", {}),
                }
            )

        return resources

    def _needs_confirmation(self, action_type: ActionType) -> bool:
        """Determine if action requires user confirmation.

        Args:
            action_type: The action being performed

        Returns:
            True if confirmation required, False otherwise
        """
        destructive_actions = {
            ActionType.DELETE_MODEL,
            ActionType.SCALE_MODEL,
            ActionType.DELETE_NOTEBOOK,
            ActionType.STOP_NOTEBOOK,
        }

        return action_type in destructive_actions

    def _resolve_from_context(
        self, context: list[dict[str, str]], resource_type: str
    ) -> str | None:
        """Resolve resource reference from conversation context.

        Args:
            context: Conversation history
            resource_type: Type of resource to resolve (e.g., "model")

        Returns:
            Resource name if found, None otherwise
        """
        if not context:
            return None

        # Search backwards through context for resource mentions
        for message in reversed(context):
            content = message.get("content", "").lower()

            # Multiple patterns to catch different phrasings
            patterns = [
                r"([a-z0-9\-]+)\s+model",  # "sentiment-analysis model"
                r"model\s+(?:named\s+|called\s+)?([a-z0-9\-]+)",  # "model named X"
                r"status\s+of\s+([a-z0-9\-]+)",  # "status of X"
                r"the\s+([a-z0-9\-]+)\s+(?:model|is)",  # "the X model"
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    name = match.group(1)
                    # Filter out common words
                    if name not in ["the", "a", "an", "my", "your"]:
                        return name

        return None

    def _convert_number_word_to_int(self, text: str) -> int | None:
        """Convert number words to integers.

        Args:
            text: Text that might contain number words

        Returns:
            Integer value if conversion successful, None otherwise
        """
        number_words = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }

        text_lower = text.lower().strip()
        return number_words.get(text_lower)

    async def validate_request(self, intent: UserIntent) -> None:
        """Validate that intent has all required parameters.

        Args:
            intent: User intent to validate

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Deployment requires model_name
        if intent.action_type == ActionType.DEPLOY_MODEL:
            if "model_name" not in intent.parameters:
                raise ValueError("Model deployment requires a model name")

        # Scaling requires model_name and replicas
        if intent.action_type == ActionType.SCALE_MODEL:
            if "model_name" not in intent.parameters:
                raise ValueError("Model scaling requires a model name")
            if "replicas" not in intent.parameters:
                raise ValueError("Model scaling requires replica count")

            # Validate replica count
            replicas = intent.parameters.get("replicas")
            if not isinstance(replicas, int):
                # Try to convert number words
                converted = self._convert_number_word_to_int(str(replicas))
                if converted is not None:
                    intent.parameters["replicas"] = converted
                else:
                    raise ValueError(
                        f"Replica count must be a number, got: {replicas}"
                    )

            # Check range
            if intent.parameters["replicas"] < 0 or intent.parameters["replicas"] > 100:
                raise ValueError(
                    f"Replica count must be between 0 and 100, got: {intent.parameters['replicas']}"
                )

        # Deletion requires model_name
        if intent.action_type == ActionType.DELETE_MODEL:
            if "model_name" not in intent.parameters:
                raise ValueError("Model deletion requires a model name")

        # Get status requires model_name
        if intent.action_type == ActionType.GET_STATUS:
            if "model_name" not in intent.parameters:
                raise ValueError("Status query requires a model name")

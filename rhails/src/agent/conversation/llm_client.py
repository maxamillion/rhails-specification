"""LLM client wrapper for lightspeed-stack integration."""

import os

import httpx
import yaml


class LLMClient:
    """Wrapper for lightspeed-stack LLM provider.

    Integrates with on-cluster vLLM endpoint (Llama 3.3-70B) for
    intent parsing and natural language generation.
    """

    def __init__(self, config_path: str | None = None):
        """Initialize LLM client.

        Args:
            config_path: Path to lightspeed-stack.yaml configuration
                        (defaults to OLS_CONFIG_FILE env var)
        """
        self.config_path = config_path or os.getenv(
            "OLS_CONFIG_FILE", "./lightspeed-stack.yaml"
        )
        self._load_config()
        self._initialize_client()

    def _load_config(self) -> None:
        """Load configuration from lightspeed-stack.yaml."""
        with open(self.config_path) as f:
            config = yaml.safe_load(f)

        # Extract LLM provider configuration
        providers = config.get("providers", {})
        inference_providers = providers.get("inference", [])

        if not inference_providers:
            raise ValueError("No inference providers configured in lightspeed-stack.yaml")

        # Use first inference provider
        self.provider_config = inference_providers[0]
        self.provider_type = self.provider_config.get("type", "vllm")
        self.base_url = self.provider_config.get("base_url")
        self.model = self.provider_config.get("model")
        self.tool_calling = self.provider_config.get("tool_calling", False)

        # Model parameters
        self.temperature = self.provider_config.get("temperature", 0.7)
        self.max_tokens = self.provider_config.get("max_tokens", 2048)
        self.top_p = self.provider_config.get("top_p", 0.95)

        # Resolve environment variables in base_url
        if self.base_url and "${env." in self.base_url:
            import re

            matches = re.findall(r'\$\{env\.([^}]+)\}', self.base_url)
            for match in matches:
                parts = match.split(":-")
                env_var = parts[0]
                default = parts[1] if len(parts) > 1 else None
                value = os.getenv(env_var, default)
                self.base_url = self.base_url.replace(f"${{env.{match}}}", value or "")

    def _initialize_client(self) -> None:
        """Initialize HTTP client for LLM endpoint."""
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text from LLM.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            temperature: Sampling temperature (optional, uses config default)
            max_tokens: Max tokens to generate (optional, uses config default)

        Returns:
            Generated text response
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "top_p": self.top_p,
        }

        response = await self.http_client.post(
            "/v1/chat/completions",
            json=request_data,
        )
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"]

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None = None,
    ) -> dict:
        """Generate with function calling/tool use.

        Args:
            prompt: User prompt
            tools: List of tool definitions (OpenAI format)
            system_prompt: System prompt (optional)

        Returns:
            Generated response with tool calls if applicable
        """
        if not self.tool_calling:
            raise ValueError("Tool calling not enabled for this LLM provider")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_data = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        response = await self.http_client.post(
            "/v1/chat/completions",
            json=request_data,
        )
        response.raise_for_status()

        return response.json()

    async def parse_intent(
        self, user_query: str, conversation_context: list[dict] | None = None
    ) -> dict:
        """Parse user intent from natural language query.

        Args:
            user_query: User's natural language input
            conversation_context: Previous conversation messages (optional)

        Returns:
            Parsed intent including action_type, target_resources, parameters, confidence
        """
        system_prompt = """You are an AI assistant that parses user intents for OpenShift AI operations.

Extract the following from the user's query:
- action_type: The operation type (deploy_model, list_models, create_pipeline, etc.)
- target_resources: Resources mentioned (model names, pipeline names, etc.)
- parameters: Operation parameters (replicas, memory, schedule, etc.)
- confidence: Your confidence level (0.0 to 1.0)
- ambiguities: Any unclear aspects that need clarification

Respond in JSON format."""

        # Build context-aware prompt
        prompt_parts = []
        if conversation_context:
            prompt_parts.append("Previous conversation:")
            for msg in conversation_context[-5:]:  # Last 5 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role}: {content}")
            prompt_parts.append("")

        prompt_parts.append(f"User query: {user_query}")
        prompt_parts.append("\nParse this intent and respond with JSON.")

        prompt = "\n".join(prompt_parts)

        response = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for more consistent parsing
        )

        # Parse JSON response
        import json

        try:
            intent = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: Extract JSON from markdown code blocks
            import re

            json_match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
            if json_match:
                intent = json.loads(json_match.group(1))
            else:
                # Return low-confidence intent with the raw response
                intent = {
                    "action_type": "unknown",
                    "target_resources": [],
                    "parameters": {},
                    "confidence": 0.0,
                    "ambiguities": [f"Failed to parse LLM response: {response}"],
                }

        return intent

    async def generate_response(
        self,
        user_query: str,
        operation_results: list[dict],
        conversation_context: list[dict] | None = None,
    ) -> str:
        """Generate user-friendly response from operation results.

        Args:
            user_query: Original user query
            operation_results: Results from executed operations
            conversation_context: Previous conversation messages (optional)

        Returns:
            Natural language response for the user
        """
        system_prompt = """You are an AI assistant helping users manage OpenShift AI.

Generate a clear, concise response based on the operation results.
- Be helpful and conversational
- Explain technical details in user-friendly language
- If there were errors, provide actionable guidance
- Keep responses focused and relevant"""

        # Build prompt with context
        prompt_parts = []
        if conversation_context:
            prompt_parts.append("Previous conversation:")
            for msg in conversation_context[-3:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role}: {content}")
            prompt_parts.append("")

        prompt_parts.append(f"User query: {user_query}")
        prompt_parts.append(f"\nOperation results: {operation_results}")
        prompt_parts.append("\nGenerate a user-friendly response.")

        prompt = "\n".join(prompt_parts)

        return await self.generate(prompt=prompt, system_prompt=system_prompt)

    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()

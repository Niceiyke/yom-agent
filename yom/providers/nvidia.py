"""NVIDIA NIM provider - supports OpenAI-compatible NVIDIA endpoints."""

from __future__ import annotations

from typing import Any

from yom.providers.openai import OpenAIProvider


class NVIDIAProvider(OpenAIProvider):
    """Provider for NVIDIA NIM (NVIDIA Inference Microservices).
    
    Uses OpenAI-compatible API at https://integrate.api.nvidia.com/v1
    
    Args:
        api_key: NVIDIA API key (get from https://ngc.nvidia.com)
        model: Model ID (e.g., "qwen/qwen3-coder-480b-a35b-instruct")
        **kwargs: Additional arguments passed to OpenAI client
    
    Example:
        ```python
        from yom.providers.nvidia import NVIDIAProvider
        
        provider = NVIDIAProvider(
            api_key="nvapi-xxx",
            model="qwen/qwen3-coder-480b-a35b-instruct"
        )
        ```
    """
    
    provider_name = "nvidia"
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "qwen/qwen3-coder-480b-a35b-instruct",
        base_url: str = "https://integrate.api.nvidia.com/v1",
        **kwargs: Any,
    ):
        # Get API key from env if not provided
        if api_key is None:
            import os
            api_key = os.environ.get("NVIDIA_API_KEY", "")
        
        super().__init__(
            api_key=api_key,
            base_url=base_url,
        )
        
        # Store default model for this provider
        self._default_model = model

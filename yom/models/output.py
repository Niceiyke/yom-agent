"""Output validation for agent responses using Pydantic."""

from __future__ import annotations

import re
from typing import Any, Generic, TypeVar, Self

from pydantic import BaseModel, Field, ValidationError

from yom.tools.result import ToolResult


# Type variable for output type
T = TypeVar("T")


class OutputValidationError(Exception):
    """Raised when output validation fails."""
    def __init__(self, errors: list[str], attempts: int = 1):
        self.errors = errors
        self.attempts = attempts
        super().__init__(f"Output validation failed: {'; '.join(errors)}")


class AgentOutput(BaseModel, Generic[T]):
    """Validated output from an agent.
    
    Wraps the raw response and provides type-safe access to structured output.
    
    Example:
        class WeatherOutput(BaseModel):
            location: str
            temperature: float
            conditions: str
        
        output: AgentOutput[WeatherOutput] = await agent.run("What's the weather in Paris?")
        print(output.content)  # Raw text response
        print(output.result)   # Validated WeatherOutput instance
    """
    content: str  # Raw text response from the agent
    result: T | None = None  # Parsed structured output
    _raw: dict[str, Any] = {}  # Additional metadata
    
    model_config = {"arbitrary_types_allowed": True}
    
    @property
    def success(self) -> bool:
        """Check if output parsing was successful."""
        return self.result is not None
    
    @classmethod
    def from_text(
        cls,
        text: str,
        output_type: type[T],
        max_retries: int = 3,
    ) -> Self:
        """Parse text into the output type, with retry logic.
        
        Args:
            text: Raw text response from agent
            output_type: Pydantic model to parse into
            max_retries: Maximum number of retry attempts (for retry-on-failure)
        
        Returns:
            AgentOutput instance with parsed result
            
        Raises:
            OutputValidationError: If all parsing attempts fail
        """
        errors: list[str] = []
        
        for attempt in range(max_retries):
            try:
                # Try to parse as the output type
                result = output_type.model_validate_json(text)
                return cls(content=text, result=result)
            except ValidationError:
                # Try extract_and_parse
                extracted = _extract_json(text)
                if extracted:
                    try:
                        result = output_type.model_validate_json(extracted)
                        return cls(content=text, result=result)
                    except ValidationError:
                        pass
                
                # If attempt 0 failed, just record errors
                if attempt == 0:
                    # Last error will be recorded
                    pass
        
        # All attempts failed - try one more time to get errors
        extracted = _extract_json(text)
        if extracted:
            try:
                output_type.model_validate_json(extracted)
            except ValidationError as e:
                errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        else:
            errors = ["Could not extract valid JSON from response"]
        
        raise OutputValidationError(errors=errors, attempts=max_retries)


def _extract_json(text: str) -> str | None:
    """Extract JSON from text, handling thinking tags and markdown."""
    # Remove thinking/reasoning tags
    clean_text = text
    think_pattern = r'<[^>]+>([^<]+)<'
    think_match = re.search(think_pattern, text)
    if think_match:
        clean_text = text.replace(think_match.group(0), '')
    
    # Try to find JSON objects
    json_patterns = [
        r'```(?:json)?\s*(\{[^}]+\})\s*```',  # ```json ... ```
        r'(\{[^}]+\})',  # Raw { ... }
    ]
    
    for pattern in json_patterns:
        match = re.search(pattern, clean_text, re.DOTALL)
        if match:
            return match.group(1)
    
    return None


def validate_output(
    text: str,
    output_type: type[BaseModel],
    instructions: str | None = None,
) -> tuple[BaseModel | None, list[str]]:
    """Validate agent text output against a Pydantic model.
    
    Args:
        text: Raw text from agent
        output_type: Pydantic model to validate against
        instructions: Optional instructions to add context for re-validation
    
    Returns:
        Tuple of (parsed_result or None, list of error messages)
    """
    errors: list[str] = []
    result = None
    
    # Strategy 1: Try direct JSON parse
    try:
        result = output_type.model_validate_json(text.strip())
        return result, []
    except ValidationError:
        pass
    
    # Strategy 2: Extract JSON from text (handle markdown, thinking tags)
    extracted = _extract_json(text)
    if extracted:
        try:
            result = output_type.model_validate_json(extracted)
            return result, []
        except ValidationError as e:
            errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            return None, errors
    
    # All strategies failed
    errors = ["Could not extract valid JSON from response"]
    return None, errors


class AgentOutputResult(BaseModel):
    """Result wrapper for agent run with optional output validation."""
    content: str  # Raw text response
    output: Any = None  # Validated output (if output_type specified)
    validated: bool = False  # Whether validation succeeded
    validation_errors: list[str] = Field(default_factory=list)
    
    @property
    def success(self) -> bool:
        return self.validated if self.output is not None else True

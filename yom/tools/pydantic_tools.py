"""Pydantic-based tool decorators for type-safe tool definitions.

Inspired by Pydantic AI's tool system, this module provides:
- Type-safe tool parameter validation using Pydantic models
- Dependency injection via RunContext
- Automatic schema generation from Pydantic models

Example:
    from pydantic import BaseModel, Field
    from yom import Agent, tool, RunContext
    
    class MyDeps:
        db: DatabaseConn
    
    class GetWeatherInput(BaseModel):
        location: str = Field(description="City name")
        units: str = Field(default="celsius")
    
    @tool
    def get_weather(ctx: RunContext[MyDeps], location: str, units: str = "celsius") -> str:
        '''Get weather for a location'''
        return f"Weather in {location}: sunny"
    
    agent = Agent(tools=[get_weather])
"""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, Generic, TypeVar, Union, overload

from pydantic import BaseModel, ValidationError

from yom.tools.result import ToolResult

F = TypeVar("F", bound=Callable)
T = TypeVar("T")

# Type alias for dependency injection context
RunContextType = TypeVar("RunContextType")


class RunContext(Generic[T]):
    """Context object for dependency injection in tools.
    
    Provides access to dependencies (database connections, API clients, etc.)
    that are passed to the agent at runtime.
    
    Example:
        @tool
        async def get_balance(ctx: RunContext[MyDeps], account_id: str) -> str:
            balance = await ctx.deps.db.get_balance(account_id)
            return f"Balance: {balance}"
    """
    deps: T
    tool_name: str = ""
    
    def __getitem__(self, key: str) -> Any:
        """Allow attribute-style access to deps."""
        return getattr(self.deps, key)


class ToolValidationError(Exception):
    """Raised when tool argument validation fails."""
    def __init__(self, tool_name: str, errors: list[str]):
        self.tool_name = tool_name
        self.errors = errors
        super().__init__(f"Validation errors for tool '{tool_name}': {'; '.join(errors)}")


class ToolDecorator:
    """Helper to build tool metadata and handle Pydantic validation."""

    def __init__(
        self,
        name: str | None = None,
        description: str | None = None,
        parameters: dict | None = None,
        schema: dict | None = None,
        input_model: type[BaseModel] | None = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.schema = schema
        self.input_model = input_model

    def __call__(self, func: F) -> F:
        is_async = inspect.iscoroutinefunction(func)
        tool_name = self.name or func.__name__

        # Get description from docstring if not provided
        desc = self.description
        if desc is None:
            desc = func.__doc__ or f"Tool: {tool_name}"
        desc = desc.strip()

        # Build or get parameter schema
        params = self._build_parameters(func)

        # Check if function uses RunContext for dependency injection
        uses_run_context = self._uses_run_context(func)

        def bind_args(args, kwargs):
            if not args:
                return kwargs
            try:
                bound = inspect.signature(func).bind_partial(*args, **kwargs)
                return dict(bound.arguments)
            except TypeError:
                # Let the wrapped function raise a normal Python call error below.
                return kwargs

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            kwargs = bind_args(args, kwargs)
            # Validate with Pydantic model if provided
            if self.input_model:
                try:
                    validated = self.input_model(**kwargs)
                except ValidationError as e:
                    errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
                    return ToolResult(tool_name=tool_name, content="", error=f"validation_error: {'; '.join(errors)}")
                # Pass the validated model instance to the function
                result = func(validated)
            else:
                result = func(**kwargs)
            if asyncio.iscoroutine(result):
                raise TypeError(
                    f"@tool decorated function '{func.__name__}' is async, "
                    "use async def or apply @async_tool decorator"
                )
            if isinstance(result, ToolResult):
                result.tool_name = tool_name
                return result
            return ToolResult(tool_name=tool_name, content=str(result))

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            kwargs = bind_args(args, kwargs)
            # Validate with Pydantic model if provided
            if self.input_model:
                try:
                    validated = self.input_model(**kwargs)
                except ValidationError as e:
                    errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
                    return ToolResult(tool_name=tool_name, content="", error=f"validation_error: {'; '.join(errors)}")
                # Pass the validated model instance to the function
                result = func(validated)
            else:
                result = func(**kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, ToolResult):
                result.tool_name = tool_name
                return result
            return ToolResult(tool_name=tool_name, content=str(result))

        wrapper = async_wrapper if is_async else sync_wrapper
        wrapper._tool_name = tool_name
        wrapper._tool_description = desc
        wrapper._tool_parameters = params
        wrapper._tool_func = func
        wrapper._tool_schema_version = "1.0"
        wrapper._tool_input_model = self.input_model
        wrapper._tool_uses_run_context = uses_run_context

        return wrapper

    def _uses_run_context(self, func: Callable) -> bool:
        """Check if function has a RunContext parameter."""
        sig = inspect.signature(func)
        for param in sig.parameters.values():
            ann = param.annotation
            if param.name in {"ctx", "context", "run_context"}:
                return True
            # Direct type match
            if ann is RunContext:
                return True
            # Check for generic alias RunContext[X]
            origin = getattr(ann, "__origin__", None)
            if origin is RunContext:
                return True
            # Also check parameterized generics
            if hasattr(ann, "__args__"):
                args = ann.__args__
                for arg in args:
                    if arg is RunContext:
                        return True
        return False

    def _build_parameters(self, func: Callable) -> dict:
        """Build parameters schema, excluding RunContext and using Pydantic model if provided."""
        if self.schema is not None:
            return self._normalize_schema(self.schema)
        if self.parameters is not None:
            return self._normalize_schema(self.parameters)
        if self.input_model is not None:
            return _pydantic_model_to_schema(self.input_model)
        return self._build_from_signature(func)

    def _normalize_schema(self, schema: dict) -> dict:
        """Normalize schema to always have properties wrapper."""
        if "properties" in schema:
            return schema
        return {"type": "object", "properties": schema}

    def _build_from_signature(self, func: Callable) -> dict:
        """Build parameters schema from function signature, excluding RunContext."""
        sig = inspect.signature(func)
        props = {}
        required = []
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        for pname, param in sig.parameters.items():
            ann = param.annotation
            
            # Skip RunContext parameters - they're injected, not from LLM
            if pname in {"ctx", "context", "run_context"}:
                continue
            if ann is RunContext:
                continue
            origin = getattr(ann, "__origin__", None)
            if origin is RunContext:
                continue
            
            prop = {}
            if ann != inspect.Parameter.empty and ann in type_map:
                prop["type"] = type_map[ann]
            else:
                prop["type"] = "string"

            if param.default is not inspect.Parameter.empty:
                prop["default"] = param.default
            else:
                required.append(pname)

            props[pname] = prop

        return {
            "type": "object",
            "properties": props,
            "required": required,
        }


# Try to import PydanticUndefined for checking required fields (Pydantic v2.13+)
try:
    from pydantic import PydanticUndefined
except ImportError:
    PydanticUndefined = type('Undefined', (), {'__repr__': lambda s: 'PydanticUndefined'})()


def _pydantic_model_to_schema(model: type[BaseModel]) -> dict:
    """Convert a Pydantic model to a JSON Schema for tool parameters."""
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise ValueError(f"Expected a Pydantic BaseModel class, got {type(model)}")

    properties = {}
    required = []

    # Get field definitions from model_fields (Pydantic v2)
    for field_name, field_info in model.model_fields.items():
        prop = {"type": _pydantic_type_to_json_type(field_info.annotation)}

        if field_info.description:
            prop["description"] = field_info.description

        default = field_info.default
        # Check required before default: Pydantic's missing sentinel can vary by version.
        if field_info.is_required():
            required.append(field_name)
        elif default is not None and default is not PydanticUndefined:
            prop["default"] = default

        properties[field_name] = prop

    schema = {
        "type": "object",
        "properties": properties,
    }

    if required:
        schema["required"] = required

    return schema


def _pydantic_type_to_json_type(field_type: type) -> str:
    """Convert a Pydantic type to JSON Schema type string."""
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    # Check direct type
    if field_type in type_map:
        return type_map[field_type]

    # Handle Optional and Union
    origin = getattr(field_type, "__origin__", None)
    if origin is Union:
        args = getattr(field_type, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _pydantic_type_to_json_type(non_none[0])
        # Multiple non-None types, return string as fallback
        return "string"

    if origin is not None:
        if origin is list:
            return "array"
        if origin is dict:
            return "object"

    # Default to string for complex types
    return "string"


@overload
def tool(func: F) -> F: ...


@overload
def tool(
    *,
    name: str | None = None,
    description: str | None = None,
    parameters: dict | None = None,
    schema: dict | None = None,
    input_model: type[BaseModel] | None = None,
) -> Callable[[F], F]: ...


def tool(
    func: F | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    parameters: dict | None = None,
    schema: dict | None = None,
    input_model: type[BaseModel] | None = None,
) -> F | Callable[[F], F]:
    """
    Decorator to mark a function as an agent tool with optional Pydantic validation.

    Usage:
        # Basic usage
        @tool
        def get_weather(location: str) -> str:
            '''Get weather for a location'''
            return f"Weather in {location}: sunny"

        # With Pydantic input model
        from pydantic import BaseModel, Field
        
        class GetWeatherInput(BaseModel):
            location: str = Field(description="City name")
            units: str = Field(default="celsius", description="Temperature units")
        
        @tool(input_model=GetWeatherInput)
        def get_weather(input: GetWeatherInput) -> str:
            return f"Weather in {input.location}: 22 {input.units}"

        # With dependency injection
        from dataclasses import dataclass
        
        @dataclass
        class MyDeps:
            api_key: str
        
        @tool
        def search(ctx: RunContext[MyDeps], query: str) -> str:
            return f"Searching with key {ctx.deps.api_key}..."

        # With schema
        @tool(schema={
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        })
        def search(query: str) -> str:
            return f"Results for: {query}"
    """
    if func is not None:
        return ToolDecorator(input_model=input_model)(func)
    return ToolDecorator(name=name, description=description, parameters=parameters, schema=schema, input_model=input_model)


def define_tool(
    *,
    name: str,
    description: str,
    schema: dict | None = None,
    parameters: dict | None = None,
) -> Callable[[F], F]:
    """Define a tool with explicit metadata/schema."""
    return tool(name=name, description=description, schema=schema, parameters=parameters)


def pydantic_to_schema(model: type[BaseModel]) -> dict:
    """Convert a Pydantic model to a tool JSON schema."""
    return _pydantic_model_to_schema(model)


def agent_tool(
    name: str,
    description: str,
    input_model: type[BaseModel],
) -> Callable[[F], F]:
    """
    Create a type-safe tool from a Pydantic input model.
    
    This is the recommended way to create tools with complex inputs.
    The function receives the validated Pydantic model as a single argument.
    
    Args:
        name: Tool name
        description: Tool description for LLM
        input_model: Pydantic BaseModel for input validation
    
    Example:
        class SearchInput(BaseModel):
            query: str = Field(description="Search query")
            limit: int = Field(default=10, description="Max results")
        
        @agent_tool(name="search", description="Search the web", input_model=SearchInput)
        def search(input: SearchInput) -> str:
            return f"Found {input.limit} results for '{input.query}'"
    """
    def decorator(func: Callable[[Any], Any]) -> F:
        return tool(name=name, description=description, input_model=input_model)(func)
    return decorator

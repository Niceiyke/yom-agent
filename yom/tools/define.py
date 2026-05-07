"""Define tool function for programmatic tool creation - P2."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from yom.tools.result import ToolResult

F = TypeVar("F", bound=Callable)


def define_tool(
    name: str,
    description: str,
    schema: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
    execute: Callable[..., Any] | None = None,
) -> Callable[[F], F]:
    """Define a tool programmatically without using the decorator.
    
    This is an alternative to the @tool decorator for cases where you want
    to create tools dynamically or pass them as values.
    
    Args:
        name: Tool name used in tool_calls
        description: Human-readable description for LLM context
        schema: JSON Schema for tool parameters (alternative to parameters)
        parameters: Simplified parameter spec (converted to schema internally)
        execute: The function to execute. If None, the decorated function is used.
    
    Returns:
        A decorator that wraps the function.
    
    Example:
        # Basic usage
        my_tool = define_tool(
            name="my_tool",
            description="Does something useful",
            schema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input value"}
                },
                "required": ["input"]
            }
        )(lambda input: f"Result: {input}")
        
        # With execute parameter
        def do_something(input: str) -> str:
            return f"Did: {input}"
        
        my_tool = define_tool(
            name="my_tool",
            description="Does something",
            schema={"type": "object", "properties": {"input": {"type": "string"}}},
            execute=do_something
        )
        
        # Pass to agent
        agent = Agent(tools=["core", my_tool])
    """
    def decorator(func: F) -> F:
        from yom.tools.decorator import ToolDecorator
        
        td = ToolDecorator(
            name=name,
            description=description,
            parameters=parameters,
            schema=schema,
        )
        
        wrapper = td(func)
        
        # Store execute function if provided
        if execute is not None:
            wrapper._tool_execute = execute
        
        return wrapper
    
    return decorator


def create_tool(
    name: str,
    description: str,
    schema: dict[str, Any] | None = None,
    func: Callable[..., Any] | None = None,
) -> Callable:
    """Create a tool without a decorator.
    
    Simpler interface than define_tool - provides both definition and
    immediate return of the tool.
    
    Args:
        name: Tool name
        description: Tool description
        schema: JSON Schema for parameters
        func: The function to wrap. Must be provided.
    
    Returns:
        The wrapped tool function.
    
    Example:
        def get_weather(location: str) -> str:
            return f"Weather in {location}: sunny"
        
        weather_tool = create_tool(
            name="get_weather",
            description="Get weather for a location",
            schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"]
            },
            func=get_weather,
        )
        
        agent = Agent(tools=["core", weather_tool])
    """
    if func is None:
        raise ValueError("func is required for create_tool")
    
    return define_tool(
        name=name,
        description=description,
        schema=schema,
        execute=func,
    )(func)


# =============================================================================
# Pydantic Schema Conversion - P2
# =============================================================================

def pydantic_to_schema(model: type) -> dict[str, Any]:
    """Convert a Pydantic model to a JSON Schema for tool parameters.
    
    Args:
        model: A Pydantic model class (must have pydantic annotations)
    
    Returns:
        JSON Schema dict suitable for use with define_tool or @tool.
    
    Example:
        from pydantic import BaseModel
        
        class GetWeatherInput(BaseModel):
            location: str = Field(description="City name")
            units: str = Field(default="celsius", description="Temperature units")
        
        schema = pydantic_to_schema(GetWeatherInput)
        # {
        #     "type": "object",
        #     "properties": {
        #         "location": {"type": "string", "description": "City name"},
        #         "units": {"type": "string", "description": "Temperature units", "default": "celsius"}
        #     },
        #     "required": ["location"]
        # }
    """
    try:
        from pydantic import BaseModel, Field
        from pydantic.fields import FieldInfo
    except ImportError:
        raise ImportError("pydantic is required for pydantic_to_schema. Install with: pip install pydantic")
    
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise ValueError(f"Expected a Pydantic BaseModel class, got {type(model)}")
    
    properties = {}
    required = []
    
    # Get field definitions
    annotations = getattr(model, "__annotations__", {})
    
    for field_name, field_type in annotations.items():
        field_info: FieldInfo | None = None
        default = None
        
        # Get field info from model
        if hasattr(model, "model_fields"):
            # Pydantic v2
            field_info = model.model_fields.get(field_name)
            if field_info:
                default = field_info.default
                if field_info.is_required():
                    required.append(field_name)
        elif hasattr(model, "__fields__"):
            # Pydantic v1
            field_info = model.__fields__.get(field_name)
            if field_info:
                default = field_info.default
                if field_info.required:
                    required.append(field_name)
        
        # Build property schema
        prop = {"type": _pydantic_type_to_json_type(field_type)}
        
        if field_info:
            if hasattr(field_info, "description") and field_info.description:
                prop["description"] = field_info.description
        
        if default is not None and default != ...:
            prop["default"] = default
        elif field_name not in required:
            pass  # Optional field
        
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
    from pydantic import BaseModel
    
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    
    # Check direct type
    origin = getattr(field_type, "__origin__", None)
    
    if field_type in type_map:
        return type_map[field_type]
    
    if origin is not None:
        # Handle generic types like List[str], Optional[str], etc.
        if origin is list:
            return "array"
        if origin is dict:
            return "object"
        if origin is Union:
            # For Optional (Union with NoneType)
            args = getattr(field_type, "__args__", ())
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return _pydantic_type_to_json_type(non_none[0])
    
    # Handle Optional
    if hasattr(field_type, "__args__"):
        args = field_type.__args__
        if len(args) == 2 and type(None) in args:
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                return _pydantic_type_to_json_type(non_none[0])
    
    # Default to string for complex types
    return "string"


def define_tool_from_pydantic(
    model: type,
    name: str | None = None,
    description: str | None = None,
    func: Callable[..., Any] | None = None,
) -> Callable:
    """Create a tool from a Pydantic model.
    
    Uses the Pydantic model to automatically generate the JSON Schema
    for tool parameters.
    
    Args:
        model: Pydantic BaseModel class defining the tool's input schema
        name: Tool name (defaults to function name or model name)
        description: Tool description (defaults to model docstring)
        func: Function to execute with the parsed arguments
    
    Returns:
        A tool function with automatic schema validation.
    
    Example:
        from pydantic import BaseModel
        from yom import Agent
        from yom.tools import define_tool_from_pydantic
        
        class GetWeatherInput(BaseModel):
            location: str = Field(description="City name")
            units: str = Field(default="celsius", description="Temperature units")
        
        def get_weather(input: GetWeatherInput) -> str:
            return f"Weather in {input.location}: 22 {input.units}"
        
        weather_tool = define_tool_from_pydantic(
            model=GetWeatherInput,
            name="get_weather",
            description="Get weather for a location",
            func=get_weather,
        )
        
        agent = Agent(tools=["core", weather_tool])
        await agent.run("What's the weather in Paris?")
    """
    schema = pydantic_to_schema(model)
    
    tool_name = name or (func.__name__ if func else model.__name__)
    tool_desc = description or (model.__doc__ or f"Tool: {tool_name}")
    
    def execute_with_validation(**kwargs) -> Any:
        if func is None:
            raise ValueError("func is required")
        
        # Validate and parse with Pydantic
        try:
            parsed = model(**kwargs)
        except Exception as e:
            return f"Validation error: {e}"
        
        # Call the function with parsed model
        return func(parsed)
    
    return define_tool(
        name=tool_name,
        description=tool_desc,
        schema=schema,
        execute=execute_with_validation,
    )(execute_with_validation)


# Need to import Union for type checking
from typing import Union

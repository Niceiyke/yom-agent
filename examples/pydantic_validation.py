"""Examples of using Pydantic validation in yom agents.

These examples demonstrate the Pydantic-enhanced features including:
- Tools with Pydantic input validation
- Dependency injection via RunContext
- Agent output validation with output_type
"""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from yom import Agent, RunContext, agent_tool, tool
from yom.models import AgentOutput, OutputValidationError, validate_output

# =============================================================================
# Example 1: Basic Tool with @tool decorator
# =============================================================================

@tool
def get_weather(location: str, units: str = "celsius") -> str:
    """Get weather for a location."""
    return f"Weather in {location}: sunny, 22 {units}"


# =============================================================================
# Example 2: Tool with Pydantic Input Model via agent_tool
# =============================================================================

class SearchInput(BaseModel):
    """Input schema for web search tool."""
    query: str = Field(description="The search query")
    limit: int = Field(default=10, description="Maximum number of results")
    region: str = Field(default="us", description="Search region code")


@agent_tool(
    name="web_search",
    description="Search the web for information",
    input_model=SearchInput,
)
def web_search(input: SearchInput) -> str:
    """Search the web and return results."""
    return f"Found {input.limit} results for '{input.query}' in region {input.region}"


# =============================================================================
# Example 3: Tool with Dependency Injection via RunContext
# =============================================================================

@dataclass
class DatabaseDeps:
    """Dependencies for database tools."""
    connection_string: str
    timeout: int = 30


@tool
def get_user(ctx: RunContext[DatabaseDeps], user_id: str) -> str:
    """Get a user from the database."""
    return f"User {user_id} from {ctx.deps.connection_string} (timeout: {ctx.deps.timeout}s)"


# =============================================================================
# Example 4: Agent with Output Validation
# =============================================================================

class WeatherOutput(BaseModel):
    """Expected output structure for weather queries."""
    location: str = Field(description="City name")
    temperature: float = Field(description="Temperature in Celsius")
    conditions: str = Field(description="Weather conditions")
    humidity: int = Field(description="Humidity percentage", ge=0, le=100)


def demonstrate_output_validation():
    """Demonstrate agent output validation.
    
    When output_type is specified, the agent's response is validated
    against the Pydantic model. If validation fails, the error is
    recorded and can be handled gracefully.
    """
    # Simulated agent response (in real usage, agent.run would return this)
    agent_response = '{"location": "Paris", "temperature": 22.5, "conditions": "sunny", "humidity": 65}'
    
    # Validate the response
    result, errors = validate_output(agent_response, WeatherOutput)
    
    if result:
        print(f"Weather in {result.location}: {result.temperature}C, {result.conditions}")
        print(f"Humidity: {result.humidity}%")
    else:
        print(f"Validation failed: {errors}")


def demonstrate_agent_output_class():
    """Demonstrate AgentOutput class for typed agent responses."""
    # Create an output wrapper
    raw_response = '{"location": "Tokyo", "temperature": 18.0, "conditions": "cloudy", "humidity": 72}'
    
    try:
        output = AgentOutput.from_text(raw_response, WeatherOutput)
        print(f"Content (raw): {output.content}")
        print(f"Result (parsed): {output.result}")
        print(f"Success: {output.success}")
        
        # Access typed fields
        if output.result:
            print(f"City: {output.result.location}")
            print(f"Temp: {output.result.temperature}")
    except OutputValidationError as e:
        print(f"Failed after {e.attempts} attempts: {e.errors}")


# =============================================================================
# Example 5: Using Pydantic Models for Agent State
# =============================================================================

def demonstrate_models():
    """Show how Pydantic models provide validation."""
    from yom.models import AgentState

    # Create state with validation
    state = AgentState.create(
        runtime_id="my-agent",
        session_id="session-123",
    )

    # Add messages (type-safe)
    state.add_user_message("Hello, world!")
    state.add_assistant_message("Hi there!")

    # Serialize to dict (validated)
    data = state.to_dict()
    print(f"State has {len(state.messages)} messages")

    # Load from dict (validated)
    loaded = AgentState.from_dict(data)
    print(f"Loaded state: {loaded.session_id}")

    # Invalid data raises error (validated by Pydantic)
    try:
        bad_data = {"session_id": "s1", "runtime_id": "r1", "messages": [{"role": "invalid", "content": "x"}]}
        AgentState.from_dict(bad_data)
    except (ValueError, Exception) as e:
        print(f"Validation caught: {type(e).__name__}")


# =============================================================================
# Example 6: Complete Agent Setup with Output Validation
# =============================================================================

def create_agent_with_tools():
    """Create an agent with Pydantic-validated tools."""
    agent = Agent(
        tools=["core", get_weather, web_search, get_user],
        system_prompt="You are a helpful assistant with access to weather and search tools.",
    )
    return agent


if __name__ == "__main__":
    print("=== Pydantic Validation Examples ===\n")
    
    print("--- Model Validation ---")
    demonstrate_models()
    
    print("\n--- Output Validation ---")
    demonstrate_output_validation()
    
    print("\n--- AgentOutput Class ---")
    demonstrate_agent_output_class()

    print("\n--- Example Agent ---")
    agent = create_agent_with_tools()
    print(f"Agent created with tools: {agent.available_tools}")
    
    # Test tool directly
    result = get_weather(location="Paris")
    print(f"Weather tool result: {result.content}")

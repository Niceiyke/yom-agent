"""Example yom plugin: Custom tools and middleware."""

from yom import tool
from yom.plugins import MiddlewarePlugin, ToolPlugin


class ExampleToolsPlugin(ToolPlugin):
    """Plugin providing example tools."""

    name = "example-tools"
    version = "1.0.0"
    description = "Example tools for demonstration"

    def get_tools(self):
        return [
            calculate_math,
            format_date,
            validate_email,
            generate_id,
        ]


class ExampleMiddlewarePlugin(MiddlewarePlugin):
    """Plugin providing example middleware."""

    name = "example-middleware"
    version = "1.0.0"
    description = "Request/response logging middleware"

    def get_middleware(self):
        return [
            request_logger,
            response_timer,
        ]


# =============================================================================
# Example Tools
# =============================================================================

@tool(
    name="calculate_math",
    description="Evaluate a mathematical expression safely"
)
def calculate_math(expression: str) -> str:
    """Evaluate a math expression without using eval."""
    import ast
    import operator

    SAFE_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def safe_eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = safe_eval(node.left)
            right = safe_eval(node.right)
            return SAFE_OPS[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            return SAFE_OPS[type(node.op)](safe_eval(node.operand))
        else:
            raise ValueError(f"Unsafe expression: {ast.dump(node)}")

    try:
        tree = ast.parse(expression, mode="eval")
        result = safe_eval(tree.body)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}"


@tool(
    name="format_date",
    description="Format a date string"
)
def format_date(date_str: str, format_str: str = "%Y-%m-%d") -> str:
    """Format a date string."""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime(format_str)
    except Exception as e:
        return f"Error: {e}"


@tool(
    name="validate_email",
    description="Validate an email address"
)
def validate_email(email: str) -> str:
    """Validate an email address format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, email):
        return "Valid email address"
    return "Invalid email address"


@tool(
    name="generate_id",
    description="Generate a unique ID"
)
def generate_id(prefix: str = "id") -> str:
    """Generate a unique ID."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Example Middleware
# =============================================================================

async def request_logger(request: dict, next_handler) -> dict:
    """Log incoming requests."""
    import logging
    logger = logging.getLogger("yom.middleware")
    logger.info(f"Request: {request.get('prompt', '')[:100]}...")
    return await next_handler(request)


async def response_timer(request: dict, next_handler) -> dict:
    """Time the response."""
    import time
    start = time.time()
    result = await next_handler(request)
    elapsed = time.time() - start
    result["_timing"] = elapsed
    return result

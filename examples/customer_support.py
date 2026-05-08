"""Real-world example: Customer Support Agent with Output Validation.

This example demonstrates a production-ready customer support agent that:
1. Uses Pydantic for both tool inputs AND output validation
2. Makes real API calls to a LLM (MiniMax or OpenAI)
3. Returns structured, type-safe responses

Run: python examples/customer_support.py
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from yom import Agent, tool


# =============================================================================
# Domain Models - Define the data structures for our domain
# =============================================================================

class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SupportOutput(BaseModel):
    """Structured output for customer support responses."""
    response: str = Field(description="The support agent's response to the customer")
    action_taken: str = Field(description="What action was taken (e.g., 'refunded', 'escalated', 'info_provided')")
    ticket_status: TicketStatus = Field(description="Updated ticket status")
    priority: Priority = Field(description="Priority level for the ticket")
    needs_escalation: bool = Field(description="Whether this ticket needs human escalation")
    follow_up_required: bool = Field(description="Whether follow-up is needed")


class CustomerInfo(BaseModel):
    """Customer information extracted from query."""
    name: str = Field(description="Customer's name")
    email: str = Field(description="Customer's email")
    account_type: Literal["free", "pro", "enterprise"] = Field(description="Account tier")


class OrderInfo(BaseModel):
    """Order information for refund requests."""
    order_id: str = Field(description="Order ID")
    amount: float = Field(description="Order amount in USD")
    status: str = Field(description="Order status")


# =============================================================================
# Support Tools - Tools the agent can use
# =============================================================================

@dataclass
class SupportDeps:
    """Dependencies for support tools (simulated database)."""
    db_path: str = "/tmp/support_db"


@tool
def lookup_customer(ctx: SupportDeps, email: str) -> str:
    """Look up customer information by email."""
    # In production, this would query a real database
    return f'Customer found: John Doe, Pro account, customer since 2023'


@tool
def lookup_order(ctx: SupportDeps, order_id: str) -> str:
    """Look up order details by order ID."""
    # In production, this would query a real database
    return f'Order {order_id}: $99.00, delivered 2024-01-15, status: delivered'


@tool
def process_refund(ctx: SupportDeps, order_id: str, reason: str) -> str:
    """Process a refund for an order."""
    # In production, this would interact with payment system
    return f'Refund processed for order {order_id}. Reason: {reason}. Amount: $99.00'


@tool
def create_support_ticket(
    ctx: SupportDeps,
    customer_email: str,
    subject: str,
    priority: str,
    description: str
) -> str:
    """Create a new support ticket."""
    # In production, this would create a ticket in the ticketing system
    return f'Ticket created: {subject} (priority: {priority}) for {customer_email}'


@tool
def escalate_to_human(ctx: SupportDeps, ticket_id: str, reason: str) -> str:
    """Escalate a ticket to human support."""
    return f'Ticket {ticket_id} escalated to human support. Reason: {reason}'


# =============================================================================
# Output Validation - Ensure LLM responses are well-formed
# =============================================================================

SYSTEM_PROMPT = """You are a helpful customer support agent.

When responding to customers:
1. Be polite and professional
2. Gather necessary information
3. Take appropriate action (refund, ticket, info, escalation)
4. Always respond with a valid JSON object containing:
   - response: your response text to the customer
   - action_taken: what you did (refunded, ticket_created, info_provided, escalated)
   - ticket_status: open, in_progress, resolved, or closed
   - priority: low, medium, high, or urgent
   - needs_escalation: true or false
   - follow_up_required: true or false

Example valid response:
{"response": "I've processed your refund of $99.00.", "action_taken": "refunded", "ticket_status": "resolved", "priority": "medium", "needs_escalation": false, "follow_up_required": false}
"""


async def validate_support_output(text: str) -> tuple[SupportOutput | None, list[str]]:
    """Validate LLM response against SupportOutput model."""
    from yom.models import validate_output
    
    result, errors = validate_output(text, SupportOutput)
    
    if errors:
        return None, errors
    
    return result, []


# =============================================================================
# Main Agent - Put it all together
# =============================================================================

async def main():
    print("=" * 60)
    print("Customer Support Agent - Real World Example")
    print("=" * 60)
    print()
    
    # Create the agent with all tools
    agent = Agent(
        tools=[
            "core",  # Built-in file tools
            lookup_customer,
            lookup_order,
            process_refund,
            create_support_ticket,
            escalate_to_human,
        ],
        system_prompt=SYSTEM_PROMPT,
    )
    
    print(f"Agent created with tools: {agent.available_tools}")
    print()
    
    # Simulate customer queries
    queries = [
        "Hi, I want to refund my order #12345. It never arrived.",
        "My account was charged twice this month. Can you help?",
        "I can't log in to my account. My password isn't working.",
    ]
    
    for query in queries:
        print(f"Customer: {query}")
        print("-" * 40)
        
        try:
            # Run the agent
            response = await agent.run(query)
            
            print(f"Raw response: {response[:200]}...")
            print()
            
            # Validate the output
            validated, errors = await validate_support_output(response)
            
            if validated:
                print(f"✅ Action: {validated.action_taken}")
                print(f"   Response: {validated.response[:100]}...")
                print(f"   Status: {validated.ticket_status}")
                print(f"   Priority: {validated.priority}")
                print(f"   Escalation: {validated.needs_escalation}")
                print(f"   Follow-up: {validated.follow_up_required}")
            else:
                print(f"❌ Validation failed: {errors}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()
        print("-" * 40)
        print()
    
    # Example with session persistence
    print("=" * 60)
    print("Session Persistence Example")
    print("=" * 60)
    print()
    
    customer_agent = Agent(
        session_id="customer-123",
        tools=["core"],
        system_prompt="You are helping a customer named Alice.",
    )
    
    await customer_agent.run("My name is Alice")
    print("Remembered: My name is Alice")
    
    response = await customer_agent.run("What is my name?")
    print(f"Query: What is my name?")
    print(f"Response: {response}")
    
    # Cleanup
    await customer_agent.dispose()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Production example: Customer support with sub-agents.

This example shows a realistic customer support scenario:
1. User reports an issue
2. Coordinator spawns specialist agents:
   - Data lookup agent
   - Refund processing agent
3. Coordinator synthesizes results into a response

Run:
    export MINIMAX_API_KEY=your_key
    python examples/production/customer_support.py
"""

import asyncio
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import BaseModel, Field

from yom import Agent, RunContext, tool

# =============================================================================
# Domain Models
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
    """Structured output for support responses."""
    response: str = Field(description="Response to customer")
    action_taken: str = Field(description="Action taken (refunded, ticket_created, etc.)")
    ticket_status: TicketStatus
    priority: Priority
    needs_escalation: bool
    follow_up_required: bool


# =============================================================================
# Support Tools
# =============================================================================

@dataclass
class SupportDeps:
    db_path: str = "/tmp/support_db"


@tool
def lookup_customer(ctx: RunContext[SupportDeps], email: str) -> str:
    """Look up customer information by email."""
    return "Customer: John Doe, Pro account, customer since 2023"


@tool
def lookup_order(ctx: RunContext[SupportDeps], order_id: str) -> str:
    """Look up order details."""
    return f"Order {order_id}: $99.00, delivered 2024-01-15, status: delivered"


@tool
def process_refund(ctx: RunContext[SupportDeps], order_id: str, reason: str) -> str:
    """Process a refund for an order."""
    return f"Refund processed for order {order_id}. Reason: {reason}. Amount: $99.00"


@tool
def create_ticket(
    ctx: RunContext[SupportDeps],
    customer_email: str,
    subject: str,
    priority: str,
    description: str
) -> str:
    """Create a support ticket."""
    return f"Ticket created: {subject} (priority: {priority}) for {customer_email}"


@tool
def escalate(ctx: RunContext[SupportDeps], ticket_id: str, reason: str) -> str:
    """Escalate to human support."""
    return f"Ticket {ticket_id} escalated. Reason: {reason}"


# =============================================================================
# Support Agent
# =============================================================================

SYSTEM_PROMPT = """You are a customer support agent. When responding:
1. Be polite and professional
2. Gather necessary information
3. Take appropriate action (refund, ticket, or escalation)
4. Always respond with valid JSON containing:
   - response: your response to the customer
   - action_taken: what you did
   - ticket_status: open, in_progress, resolved, or closed
   - priority: low, medium, high, or urgent
   - needs_escalation: true or false
   - follow_up_required: true or false

Example response:
{"response": "I've processed your refund.", "action_taken": "refunded", "ticket_status": "resolved", "priority": "medium", "needs_escalation": false, "follow_up_required": false}
"""


async def main():
    print("=" * 60)
    print("Customer Support Agent - Production Example")
    print("=" * 60)
    print()
    
    # Create agent with tools
    agent = Agent(
        tools=["core", lookup_customer, lookup_order, process_refund, create_ticket, escalate],
        system_prompt=SYSTEM_PROMPT,
        session_id="support-demo",
    )
    
    print(f"Tools: {agent.available_tools}")
    print()
    
    # Sample queries
    queries = [
        "Hi, I want to refund my order #12345. It never arrived.",
        "My account was charged twice this month. Can you help?",
        "I can't log in to my account. My password isn't working.",
    ]
    
    for query in queries:
        print(f"Customer: {query}")
        print("-" * 40)
        
        try:
            response = await agent.run(query)
            
            print(f"Response: {response[:200]}...")
            
            # Try to parse as JSON
            import json
            try:
                data = json.loads(response)
                print(f"  Action: {data.get('action_taken')}")
                print(f"  Status: {data.get('ticket_status')}")
                print(f"  Priority: {data.get('priority')}")
                print(f"  Escalation: {data.get('needs_escalation')}")
            except json.JSONDecodeError:
                print("  (Could not parse as JSON)")
                
        except Exception as e:
            print(f"Error: {e}")
        
        print()
        print("=" * 40)
        print()
    
    # Show session
    messages = await agent.get_session_messages()
    print(f"Session has {len(messages)} messages")


if __name__ == "__main__":
    asyncio.run(main())

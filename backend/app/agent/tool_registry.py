"""
Tool registry for the agent system.

This module defines the available tools and provides a registry pattern
for the agent to select and execute tools dynamically.

Interview line: "I used a tool registry pattern so the agent can dynamically
discover and invoke tools. This makes it easy to add new tools without
modifying the core agent loop, and each tool is independently testable."
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import search_web, research_company
from app.agent.calendar_tool import schedule_interview, list_upcoming_events, check_availability
from app.agent.email_tool import generate_follow_up_email, generate_thank_you_email, generate_networking_email


class ToolName(str, Enum):
    """Available tools in the agent system."""
    WEB_SEARCH = "web_search"
    RESEARCH_COMPANY = "research_company"
    SCHEDULE_INTERVIEW = "schedule_interview"
    CHECK_AVAILABILITY = "check_availability"
    LIST_EVENTS = "list_events"
    GENERATE_FOLLOW_UP = "generate_follow_up"
    GENERATE_THANK_YOU = "generate_thank_you"
    GENERATE_NETWORKING = "generate_networking"


@dataclass
class ToolDefinition:
    """Definition of a tool available to the agent."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema style
    required_params: List[str]
    handler: Callable


# Tool definitions with JSON Schema parameters (for LLM tool calling)
TOOL_DEFINITIONS: Dict[str, ToolDefinition] = {
    ToolName.WEB_SEARCH: ToolDefinition(
        name="web_search",
        description="Search the web for information. Use this to look up company details, recent news, or any external information needed for personalizing application materials.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5
                }
            },
            "required": ["query"]
        },
        required_params=["query"],
        handler=search_web
    ),

    ToolName.RESEARCH_COMPANY: ToolDefinition(
        name="research_company",
        description="Research a company for cover letter personalization. Returns structured information about the company's mission, products, recent news, and culture.",
        parameters={
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Name of the company to research"
                }
            },
            "required": ["company_name"]
        },
        required_params=["company_name"],
        handler=research_company
    ),

    ToolName.SCHEDULE_INTERVIEW: ToolDefinition(
        name="schedule_interview",
        description="Schedule an interview on the user's calendar. Creates a calendar event with reminders.",
        parameters={
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Name of the company"
                },
                "role_title": {
                    "type": "string",
                    "description": "Role being interviewed for"
                },
                "start_time": {
                    "type": "string",
                    "description": "Interview start time (ISO format)"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Interview duration in minutes",
                    "default": 60
                },
                "location": {
                    "type": "string",
                    "description": "Interview location or video call URL"
                }
            },
            "required": ["company_name", "role_title", "start_time"]
        },
        required_params=["company_name", "role_title", "start_time"],
        handler=schedule_interview
    ),

    ToolName.CHECK_AVAILABILITY: ToolDefinition(
        name="check_availability",
        description="Check the user's calendar availability for a given date range.",
        parameters={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start of date range (ISO format)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End of date range (ISO format)"
                }
            },
            "required": ["start_date", "end_date"]
        },
        required_params=["start_date", "end_date"],
        handler=check_availability
    ),

    ToolName.LIST_EVENTS: ToolDefinition(
        name="list_events",
        description="List upcoming calendar events (interviews, follow-ups, deadlines).",
        parameters={
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "Number of days to look ahead",
                    "default": 7
                },
                "event_type": {
                    "type": "string",
                    "description": "Filter by event type: interview, follow_up, deadline",
                    "enum": ["interview", "follow_up", "deadline"]
                }
            }
        },
        required_params=[],
        handler=list_upcoming_events
    ),

    ToolName.GENERATE_FOLLOW_UP: ToolDefinition(
        name="generate_follow_up",
        description="Generate a follow-up email for a job application. Creates a draft for user review.",
        parameters={
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "string",
                    "description": "UUID of the application to follow up on"
                },
                "user_id": {
                    "type": "string",
                    "description": "UUID of the user"
                }
            },
            "required": ["application_id", "user_id"]
        },
        required_params=["application_id", "user_id"],
        handler=None  # Requires db session, handled specially
    ),

    ToolName.GENERATE_THANK_YOU: ToolDefinition(
        name="generate_thank_you",
        description="Generate a thank-you email after an interview. Creates a draft for user review.",
        parameters={
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "string",
                    "description": "UUID of the application"
                },
                "user_id": {
                    "type": "string",
                    "description": "UUID of the user"
                },
                "interviewer_name": {
                    "type": "string",
                    "description": "Name of the interviewer"
                },
                "interview_date": {
                    "type": "string",
                    "description": "Date/time of the interview"
                },
                "topics_discussed": {
                    "type": "string",
                    "description": "Key topics discussed in the interview"
                }
            },
            "required": ["application_id", "user_id", "interviewer_name", "interview_date"]
        },
        required_params=["application_id", "user_id", "interviewer_name", "interview_date"],
        handler=None  # Requires db session
    ),

    ToolName.GENERATE_NETWORKING: ToolDefinition(
        name="generate_networking",
        description="Generate a networking outreach email. Creates a draft for user review.",
        parameters={
            "type": "object",
            "properties": {
                "recipient_name": {
                    "type": "string",
                    "description": "Name of the person to reach out to"
                },
                "recipient_role": {
                    "type": "string",
                    "description": "Their role/title"
                },
                "company_name": {
                    "type": "string",
                    "description": "Their company"
                },
                "user_id": {
                    "type": "string",
                    "description": "UUID of the user"
                },
                "your_background": {
                    "type": "string",
                    "description": "Brief summary of your background"
                },
                "why_reaching_out": {
                    "type": "string",
                    "description": "Reason for reaching out"
                }
            },
            "required": ["recipient_name", "recipient_role", "company_name", "user_id", "your_background", "why_reaching_out"]
        },
        required_params=["recipient_name", "recipient_role", "company_name", "user_id", "your_background", "why_reaching_out"],
        handler=None  # Requires db session
    ),
}


class ToolRegistry:
    """
    Registry for agent tools.

    Provides:
    - Tool discovery (list available tools)
    - Tool execution (invoke tool by name)
    - Tool validation (check parameters)

    Usage:
        registry = ToolRegistry(db)
        tools = registry.get_tool_definitions()
        result = await registry.execute_tool("web_search", {"query": "OpenAI news"})
    """

    def __init__(self, db: Optional[AsyncSession] = None, user_id: Optional[UUID] = None):
        self.db = db
        self.user_id = user_id
        self.definitions = TOOL_DEFINITIONS

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions in OpenAI function calling format.

        This can be passed directly to the LLM API for tool calling.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "parameters": tool_def.parameters
                }
            }
            for tool_def in self.definitions.values()
        ]

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool definition by name."""
        return self.definitions.get(name)

    def validate_params(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate tool parameters.

        Returns:
            (is_valid, error_message)
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return False, f"Unknown tool: {tool_name}"

        # Check required params
        for param in tool.required_params:
            if param not in params:
                return False, f"Missing required parameter: {param}"

        return True, None

    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool by name with given parameters.

        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters

        Returns:
            Tool execution result as a dict
        """
        # Validate
        is_valid, error = self.validate_params(tool_name, params)
        if not is_valid:
            return {"error": error}

        tool = self.get_tool(tool_name)
        if not tool:
            return {"error": f"Tool not found: {tool_name}"}

        try:
            # Handle tools that need db session
            if tool_name == ToolName.GENERATE_FOLLOW_UP:
                if not self.db or not self.user_id:
                    return {"error": "Database session required for this tool"}
                result = await generate_follow_up_email(
                    db=self.db,
                    application_id=UUID(params["application_id"]),
                    user_id=UUID(params["user_id"])
                )
                return {
                    "draft_id": result.draft_id,
                    "subject": result.subject,
                    "body": result.body,
                    "email_type": result.email_type
                }

            elif tool_name == ToolName.GENERATE_THANK_YOU:
                if not self.db or not self.user_id:
                    return {"error": "Database session required for this tool"}
                result = await generate_thank_you_email(
                    db=self.db,
                    application_id=UUID(params["application_id"]),
                    user_id=UUID(params["user_id"]),
                    interviewer_name=params["interviewer_name"],
                    interview_date=params["interview_date"],
                    topics_discussed=params.get("topics_discussed"),
                    what_excited_you=params.get("what_excited_you")
                )
                return {
                    "draft_id": result.draft_id,
                    "subject": result.subject,
                    "body": result.body,
                    "email_type": result.email_type
                }

            elif tool_name == ToolName.GENERATE_NETWORKING:
                if not self.db or not self.user_id:
                    return {"error": "Database session required for this tool"}
                result = await generate_networking_email(
                    db=self.db,
                    recipient_name=params["recipient_name"],
                    recipient_role=params["recipient_role"],
                    company_name=params["company_name"],
                    user_id=UUID(params["user_id"]),
                    your_background=params["your_background"],
                    why_reaching_out=params["why_reaching_out"],
                    shared_connection=params.get("shared_connection")
                )
                return {
                    "draft_id": result.draft_id,
                    "subject": result.subject,
                    "body": result.body,
                    "email_type": result.email_type
                }

            elif tool_name == ToolName.CHECK_AVAILABILITY:
                start_date = datetime.fromisoformat(params["start_date"])
                end_date = datetime.fromisoformat(params["end_date"])
                result = await check_availability(start_date, end_date)
                return {"busy_periods": result}

            elif tool_name == ToolName.LIST_EVENTS:
                result = await list_upcoming_events(
                    days_ahead=params.get("days_ahead", 7),
                    event_type=params.get("event_type")
                )
                return {
                    "events": [
                        {
                            "id": e.id,
                            "title": e.title,
                            "start_time": e.start_time.isoformat(),
                            "end_time": e.end_time.isoformat(),
                            "location": e.location,
                            "event_type": e.event_type
                        }
                        for e in result
                    ]
                }

            elif tool_name == ToolName.SCHEDULE_INTERVIEW:
                start_time = datetime.fromisoformat(params["start_time"])
                result = await schedule_interview(
                    company_name=params["company_name"],
                    role_title=params["role_title"],
                    start_time=start_time,
                    duration_minutes=params.get("duration_minutes", 60),
                    location=params.get("location")
                )
                return {
                    "event_id": result.id,
                    "title": result.title,
                    "start_time": result.start_time.isoformat(),
                    "location": result.location
                }

            # Tools with simple handlers
            elif tool.handler:
                if asyncio.iscoroutinefunction(tool.handler):
                    result = await tool.handler(**params)
                else:
                    result = tool.handler(**params)

                # Convert dataclass results to dict
                if hasattr(result, "__dataclass_fields__"):
                    return {
                        k: v for k, v in result.__dict__.items()
                        if not k.startswith("_")
                    }
                elif isinstance(result, list):
                    return {"results": [
                        {"title": r.title, "url": r.url, "snippet": r.snippet}
                        if hasattr(r, "title") else r
                        for r in result
                    ]}
                return result

            else:
                return {"error": f"No handler for tool: {tool_name}"}

        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}


# Import asyncio for checking coroutine functions
import asyncio


def get_tool_registry(
    db: Optional[AsyncSession] = None,
    user_id: Optional[UUID] = None
) -> ToolRegistry:
    """Get a tool registry instance."""
    return ToolRegistry(db=db, user_id=user_id)

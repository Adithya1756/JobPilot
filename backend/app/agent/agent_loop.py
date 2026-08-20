"""
Agent state machine with tool calling.

This is the core agentic loop that:
1. Receives a user request
2. Decides which tools to call (via LLM)
3. Executes tools
4. Synthesizes results
5. Returns response to user

Interview line: "I built an explicit state machine for the agent instead of
using a framework because I wanted full visibility into each step. This made
debugging much easier when the LLM made unexpected tool calls."

Flow:
1. PARSE: Understand user intent
2. PLAN: Decide which tools to call
3. EXECUTE: Run tools
4. SYNTHESIZE: Combine results into response
5. RESPOND: Return to user
"""

from typing import Dict, List, Any, Optional
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import get_llm_client
from app.agent.tool_registry import get_tool_registry, ToolRegistry, ToolName
from app.retrieval.search import hybrid_search
from app.retrieval.reranker import rerank_results
from app.agent.tools import research_company


class AgentState(str, Enum):
    """States in the agent state machine."""
    IDLE = "idle"
    PARSING = "parsing"
    PLANNING = "planning"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    RESPONDING = "responding"
    ERROR = "error"


@dataclass
class ToolCall:
    """A tool call made by the agent."""
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class AgentContext:
    """Context maintained across the agent loop."""
    user_id: UUID
    session_id: Optional[str] = None
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)
    state: AgentState = AgentState.IDLE
    error: Optional[str] = None


# System prompt for the agent
AGENT_SYSTEM_PROMPT = """You are JobPilot, an AI assistant for job applications.

You help users with:
- Drafting cover letters tailored to specific jobs
- Writing follow-up emails after applications
- Writing thank-you notes after interviews
- Scheduling interviews and setting reminders
- Researching companies

You have access to tools for web search, calendar management, and email drafting.

When a user asks you to help with a task:
1. Think about what information you need
2. Use tools to gather that information
3. Synthesize the results into a helpful response

Be concise but thorough. If you need more information from the user, ask clarifying questions.

Always explain what you're doing (e.g., "Let me research that company first...")."""


class AgentLoop:
    """
    The main agent loop with tool calling.

    This is NOT a single LLM call - it's an iterative process:
    1. Parse user request
    2. Decide which tools to call
    3. Execute tools
    4. Feed results back to LLM
    5. Continue until task is complete

    The loop is bounded by a maximum number of iterations to prevent
    infinite loops when the LLM gets stuck.
    """

    def __init__(
        self,
        db: AsyncSession,
        user_id: UUID,
        max_iterations: int = 5
    ):
        self.db = db
        self.llm = get_llm_client()
        self.registry = get_tool_registry(db=db, user_id=user_id)
        self.max_iterations = max_iterations
        self.context = AgentContext(user_id=user_id)

    async def process_message(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Process a user message through the agent loop.

        Args:
            message: User's message
            conversation_history: Previous messages in the conversation

        Returns:
            Agent response with any tool results and context
        """
        # Initialize context
        if conversation_history:
            self.context.conversation_history = conversation_history

        self.context.state = AgentState.PARSING

        # Add user message to history
        self.context.conversation_history.append({
            "role": "user",
            "content": message
        })

        # Build messages for LLM
        messages = self._build_messages(message)

        # Agent loop
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            self.context.state = AgentState.PLANNING

            try:
                # Call LLM with tools
                response = await self.llm.client.messages.create(
                    model=self.llm.model,
                    max_tokens=4096,
                    system=AGENT_SYSTEM_PROMPT,
                    messages=messages,
                    tools=self.registry.get_tool_definitions()
                )

                # Check if LLM wants to call tools
                tool_calls = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_calls.append({
                            "name": block.name,
                            "parameters": block.input,
                            "id": block.id
                        })

                if tool_calls:
                    # Execute tools
                    self.context.state = AgentState.EXECUTING
                    tool_results = []

                    for tc in tool_calls:
                        tool_call = ToolCall(
                            tool_name=tc["name"],
                            parameters=tc["parameters"]
                        )

                        # Execute
                        result = await self.registry.execute_tool(
                            tc["name"],
                            tc["parameters"]
                        )

                        tool_call.result = result
                        if result.get("error"):
                            tool_call.error = result["error"]

                        self.context.tool_calls.append(tool_call)

                        # Format for LLM
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": json.dumps(result)
                        })

                    # Add assistant response with tool calls
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    # Add tool results
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                    # Continue loop (LLM will synthesize)
                    continue

                # No tool calls - LLM is done
                self.context.state = AgentState.SYNTHESIZING

                # Extract text response
                text_response = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text_response += block.text

                # Add to conversation history
                self.context.conversation_history.append({
                    "role": "assistant",
                    "content": text_response
                })

                self.context.state = AgentState.IDLE

                return {
                    "response": text_response,
                    "tool_calls": [
                        {
                            "tool": tc.tool_name,
                            "parameters": tc.parameters,
                            "result": tc.result,
                            "error": tc.error
                        }
                        for tc in self.context.tool_calls
                    ],
                    "state": self.context.state.value
                }

            except Exception as e:
                self.context.state = AgentState.ERROR
                self.context.error = str(e)

                return {
                    "response": f"I encountered an error: {str(e)}",
                    "tool_calls": [],
                    "state": self.context.state.value,
                    "error": str(e)
                }

        # Max iterations reached
        self.context.state = AgentState.ERROR
        return {
            "response": "I'm having trouble completing this task. Could you try breaking it down into smaller steps?",
            "tool_calls": [
                {
                    "tool": tc.tool_name,
                    "parameters": tc.parameters,
                    "result": tc.result
                }
                for tc in self.context.tool_calls
            ],
            "state": self.context.state.value,
            "error": "Max iterations reached"
        }

    def _build_messages(self, current_message: str) -> List[Dict[str, Any]]:
        """Build messages array for LLM from conversation history."""
        messages = []

        # Add conversation history (excluding current message)
        for msg in self.context.conversation_history[:-1]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Add current message
        messages.append({
            "role": "user",
            "content": current_message
        })

        return messages

    async def handle_cover_letter_request(
        self,
        job_id: UUID,
        include_research: bool = True
    ) -> Dict[str, Any]:
        """
        Specialized handler for cover letter generation.

        This bypasses the general agent loop for the specific task
        of generating a cover letter, providing more control and
        traceability.

        Args:
            job_id: Job to generate cover letter for
            include_research: Whether to research the company first

        Returns:
            Generated cover letter with traceability info
        """
        from app.agent.drafting import DraftingAgent

        agent = DraftingAgent(self.db)
        result = await agent.draft_cover_letter(
            job_id=job_id,
            user_id=self.context.user_id,
            use_web_search=include_research
        )

        return {
            "draft_id": result.draft_id,
            "content": result.content,
            "retrieved_chunk_ids": result.retrieved_chunk_ids,
            "requirements": result.requirements,
            "critique": result.critique
        }

    async def handle_email_request(
        self,
        email_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Specialized handler for email generation.

        Args:
            email_type: Type of email (follow_up, thank_you, networking)
            **kwargs: Email-specific parameters

        Returns:
            Generated email draft
        """
        from app.agent.email_tool import EmailDraftingTool

        tool = EmailDraftingTool(self.db)

        if email_type == "follow_up":
            result = await tool.generate_follow_up(
                application_id=kwargs["application_id"],
                user_id=self.context.user_id
            )
        elif email_type == "thank_you":
            result = await tool.generate_thank_you(
                application_id=kwargs["application_id"],
                user_id=self.context.user_id,
                interviewer_name=kwargs["interviewer_name"],
                interview_date=kwargs["interview_date"],
                topics_discussed=kwargs.get("topics_discussed"),
                what_excited_you=kwargs.get("what_excited_you")
            )
        elif email_type == "networking":
            result = await tool.generate_networking_outreach(
                recipient_name=kwargs["recipient_name"],
                recipient_role=kwargs["recipient_role"],
                company_name=kwargs["company_name"],
                user_id=self.context.user_id,
                your_background=kwargs["your_background"],
                why_reaching_out=kwargs["why_reaching_out"],
                shared_connection=kwargs.get("shared_connection")
            )
        else:
            raise ValueError(f"Unknown email type: {email_type}")

        return {
            "draft_id": result.draft_id,
            "subject": result.subject,
            "body": result.body,
            "email_type": result.email_type
        }


async def run_agent(
    db: AsyncSession,
    user_id: UUID,
    message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Convenience function to run the agent loop.

    Args:
        db: Database session
        user_id: User ID
        message: User message
        conversation_history: Previous messages

    Returns:
        Agent response
    """
    agent = AgentLoop(db=db, user_id=user_id)
    return await agent.process_message(message, conversation_history)

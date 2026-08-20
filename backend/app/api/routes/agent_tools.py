"""
Agent chat API routes.

Provides endpoints for:
- Chatting with the agent (with tool calling)
- Generating cover letters
- Creating email drafts
- Managing calendar events

Interview line: "I exposed the agent through a chat API that returns which
tools were called and their results. This transparency is crucial for
debugging and for users to understand what the agent did."
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.agent.agent_loop import AgentLoop, run_agent
from app.agent.calendar_tool import (
    schedule_interview,
    list_upcoming_events,
    CalendarTool
)


router = APIRouter(prefix="/agent", tags=["agent"])


# Request/Response models

class ChatRequest(BaseModel):
    """Chat message to the agent."""
    message: str = Field(..., description="User message to the agent")
    conversation_history: Optional[List[dict]] = Field(
        default=None,
        description="Previous messages in the conversation"
    )


class ChatResponse(BaseModel):
    """Agent's response."""
    response: str
    tool_calls: List[dict]
    state: str
    error: Optional[str] = None


class InterviewScheduleRequest(BaseModel):
    """Request to schedule an interview."""
    company_name: str
    role_title: str
    start_time: datetime = Field(..., description="Interview start time (ISO format)")
    duration_minutes: int = Field(default=60, description="Interview duration")
    location: Optional[str] = Field(default=None, description="Interview location or video URL")
    interviewer_emails: Optional[List[str]] = Field(default=None, description="Interviewer email addresses")


class InterviewScheduleResponse(BaseModel):
    """Scheduled interview details."""
    event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    location: Optional[str]


class UpcomingEventsResponse(BaseModel):
    """List of upcoming events."""
    events: List[dict]


# Routes

@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Chat with the AI agent.

    The agent can:
    - Research companies
    - Draft cover letters
    - Generate follow-up emails
    - Schedule interviews
    - Check calendar availability

    Returns the agent's response along with any tool calls made.
    """
    result = await run_agent(
        db=db,
        user_id=current_user.id,
        message=request.message,
        conversation_history=request.conversation_history
    )

    return ChatResponse(**result)


@router.post("/schedule-interview", response_model=InterviewScheduleResponse)
async def schedule_interview_endpoint(
    request: InterviewScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Schedule an interview on the user's calendar.

    Creates a calendar event with reminders.
    In development, this uses a mock calendar.
    """
    try:
        event = await schedule_interview(
            company_name=request.company_name,
            role_title=request.role_title,
            start_time=request.start_time,
            duration_minutes=request.duration_minutes,
            location=request.location,
            interviewer_emails=request.interviewer_emails
        )

        return InterviewScheduleResponse(
            event_id=event.id,
            title=event.title,
            start_time=event.start_time,
            end_time=event.end_time,
            location=event.location
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/upcoming", response_model=UpcomingEventsResponse)
async def get_upcoming_events(
    days_ahead: int = 7,
    event_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get upcoming calendar events.

    Filters:
    - days_ahead: Number of days to look ahead (default: 7)
    - event_type: Filter by type (interview, follow_up, deadline)
    """
    events = await list_upcoming_events(
        days_ahead=days_ahead,
        event_type=event_type
    )

    return UpcomingEventsResponse(
        events=[
            {
                "id": e.id,
                "title": e.title,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat(),
                "location": e.location,
                "event_type": e.event_type
            }
            for e in events
        ]
    )


@router.post("/email/follow-up/{application_id}")
async def generate_follow_up_email(
    application_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a follow-up email for a job application.

    Creates a draft for user review before sending.
    """
    from app.agent.email_tool import generate_follow_up_email as gen_email

    try:
        draft = await gen_email(
            db=db,
            application_id=application_id,
            user_id=current_user.id
        )

        return {
            "draft_id": draft.draft_id,
            "subject": draft.subject,
            "body": draft.body,
            "email_type": draft.email_type
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/thank-you")
async def generate_thank_you_email(
    application_id: UUID,
    interviewer_name: str,
    interview_date: str,
    topics_discussed: Optional[str] = None,
    what_excited_you: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a thank-you email after an interview.

    Creates a draft for user review before sending.
    """
    from app.agent.email_tool import generate_thank_you_email as gen_email

    try:
        draft = await gen_email(
            db=db,
            application_id=application_id,
            user_id=current_user.id,
            interviewer_name=interviewer_name,
            interview_date=interview_date,
            topics_discussed=topics_discussed,
            what_excited_you=what_excited_you
        )

        return {
            "draft_id": draft.draft_id,
            "subject": draft.subject,
            "body": draft.body,
            "email_type": draft.email_type
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/networking")
async def generate_networking_email(
    recipient_name: str,
    recipient_role: str,
    company_name: str,
    your_background: str,
    why_reaching_out: str,
    shared_connection: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a networking outreach email.

    Creates a draft for user review before sending.
    """
    from app.agent.email_tool import generate_networking_email as gen_email

    try:
        draft = await gen_email(
            db=db,
            recipient_name=recipient_name,
            recipient_role=recipient_role,
            company_name=company_name,
            user_id=current_user.id,
            your_background=your_background,
            why_reaching_out=why_reaching_out,
            shared_connection=shared_connection
        )

        return {
            "draft_id": draft.draft_id,
            "subject": draft.subject,
            "body": draft.body,
            "email_type": draft.email_type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

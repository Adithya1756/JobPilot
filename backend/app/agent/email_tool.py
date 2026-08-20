"""
Email drafting tool for job application follow-ups and networking.

This tool generates email drafts (does NOT send them) for:
- Follow-up emails after applications
- Thank-you notes after interviews
- Networking outreach emails

Drafts are stored in the database for user review before sending.

Interview line: "I built an email drafting tool that generates personalized
follow-ups and thank-you notes. The key design decision was to store drafts
in the database rather than sending directly, giving users control and
preventing accidental emails."
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import GeneratedDraft, Job, Application
from app.agent.llm import get_llm_client
from app.agent.tools import research_company


# System prompts for different email types

FOLLOW_UP_SYSTEM = """You are an expert at writing professional follow-up emails for job applications.

Your emails are:
- Concise (3-4 sentences max)
- Professional but warm
- Specific to the role and company
- Action-oriented (asking for next steps)

Write the email in a natural, conversational tone. Avoid being pushy or desperate."""

FOLLOW_UP_USER = """Write a follow-up email for a job application.

**Company:** {company_name}
**Role:** {role_title}
**Days since application:** {days_since_application}
**Application status:** {application_status}
**Company info:** {company_info}

Write a brief, professional follow-up email expressing continued interest and asking about next steps.
Do not include subject line - just the email body."""

THANK_YOU_SYSTEM = """You are an expert at writing thank-you emails after job interviews.

Your emails are:
- Sent within 24 hours of interview
- Specific to the conversation topics discussed
- Reiterate enthusiasm for the role
- Reference a specific topic from the interview

Keep it brief and genuine. Avoid generic phrases."""

THANK_YOU_USER = """Write a thank-you email after an interview.

**Company:** {company_name}
**Role:** {role_title}
**Interview date:** {interview_date}
**Interviewer name:** {interviewer_name}
**Key topics discussed:** {topics_discussed}
**What excited you about the role:** {what_excited_you}

Write a brief, genuine thank-you email that references the specific conversation.
Do not include subject line - just the email body."""

NETWORKING_SYSTEM = """You are an expert at writing professional networking outreach emails.

Your emails are:
- Personalized and specific
- Clear about why you're reaching out
- Respectful of the recipient's time
- Low-pressure (no hard ask)

The goal is to start a conversation, not ask for a job directly."""

NETWORKING_USER = """Write a networking outreach email.

**Recipient name:** {recipient_name}
**Recipient role:** {recipient_role}
**Company:** {company_name}
**Your background:** {your_background}
**Why you're reaching out:** {why_reaching_out}
**Shared connection/interest:** {shared_connection}

Write a brief, personalized networking email. Be genuine and specific.
Do not include subject line - just the email body."""


@dataclass
class EmailDraft:
    """A generated email draft."""
    draft_id: str
    email_type: str  # follow_up, thank_you, networking
    recipient: Optional[str]
    subject: str
    body: str
    created_at: datetime


class EmailDraftingTool:
    """
    Tool for generating professional email drafts.

    Does NOT send emails - stores drafts for user review.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_client()

    async def generate_follow_up(
        self,
        application_id: UUID,
        user_id: UUID
    ) -> EmailDraft:
        """
        Generate a follow-up email for a job application.

        Args:
            application_id: Application to follow up on
            user_id: User who owns the application

        Returns:
            EmailDraft with follow-up content
        """
        # Get application and job details
        result = await self.db.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(Application.id == application_id)
            .where(Application.user_id == user_id)
        )
        row = result.first()

        if not row:
            raise ValueError(f"Application {application_id} not found")

        application, job = row

        # Calculate days since application
        days_since = (datetime.utcnow() - application.applied_at).days if application.applied_at else 0

        # Get company info (optional)
        company_info = "No specific information available."
        try:
            research = await research_company(job.company_name)
            if research.get("summary"):
                company_info = research["summary"][:500]  # Truncate for prompt
        except Exception:
            pass  # Continue without company info

        # Generate email
        prompt = FOLLOW_UP_USER.format(
            company_name=job.company_name,
            role_title=job.role_title,
            days_since_application=days_since,
            application_status=application.status,
            company_info=company_info
        )

        try:
            body = await self.llm.generate(
                system=FOLLOW_UP_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7
            )
        except Exception as e:
            body = f"[Error generating email: {str(e)}]"

        subject = f"Following up on {job.role_title} application"

        # Store draft
        draft_record = GeneratedDraft(
            application_id=application_id,
            draft_type="email_follow_up",
            content=body,
            metadata={
                "subject": subject,
                "recipient": None,
                "job_id": str(job.id),
                "company_name": job.company_name,
                "role_title": job.role_title
            }
        )
        self.db.add(draft_record)
        await self.db.flush()

        return EmailDraft(
            draft_id=str(draft_record.id),
            email_type="follow_up",
            recipient=None,
            subject=subject,
            body=body,
            created_at=datetime.utcnow()
        )

    async def generate_thank_you(
        self,
        application_id: UUID,
        user_id: UUID,
        interviewer_name: str,
        interview_date: str,
        topics_discussed: Optional[str] = None,
        what_excited_you: Optional[str] = None
    ) -> EmailDraft:
        """
        Generate a thank-you email after an interview.

        Args:
            application_id: Application associated with interview
            user_id: User who owns the application
            interviewer_name: Name of the interviewer
            interview_date: Date/time of interview
            topics_discussed: Key topics from the interview
            what_excited_you: What excited you about the role

        Returns:
            EmailDraft with thank-you content
        """
        # Get application and job details
        result = await self.db.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(Application.id == application_id)
            .where(Application.user_id == user_id)
        )
        row = result.first()

        if not row:
            raise ValueError(f"Application {application_id} not found")

        application, job = row

        # Generate email
        prompt = THANK_YOU_USER.format(
            company_name=job.company_name,
            role_title=job.role_title,
            interview_date=interview_date,
            interviewer_name=interviewer_name,
            topics_discussed=topics_discussed or "the role and team",
            what_excited_you=what_excited_you or "the opportunity to contribute to the team"
        )

        try:
            body = await self.llm.generate(
                system=THANK_YOU_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7
            )
        except Exception as e:
            body = f"[Error generating email: {str(e)}]"

        subject = f"Thank you for the {job.role_title} interview"

        # Store draft
        draft_record = GeneratedDraft(
            application_id=application_id,
            draft_type="email_thank_you",
            content=body,
            metadata={
                "subject": subject,
                "recipient": interviewer_name,
                "job_id": str(job.id),
                "interview_date": interview_date
            }
        )
        self.db.add(draft_record)
        await self.db.flush()

        return EmailDraft(
            draft_id=str(draft_record.id),
            email_type="thank_you",
            recipient=interviewer_name,
            subject=subject,
            body=body,
            created_at=datetime.utcnow()
        )

    async def generate_networking_outreach(
        self,
        recipient_name: str,
        recipient_role: str,
        company_name: str,
        user_id: UUID,
        your_background: str,
        why_reaching_out: str,
        shared_connection: Optional[str] = None
    ) -> EmailDraft:
        """
        Generate a networking outreach email.

        Args:
            recipient_name: Name of the person to reach out to
            recipient_role: Their role/title
            company_name: Their company
            user_id: User sending the outreach
            your_background: Brief summary of user's background
            why_reaching_out: Reason for reaching out
            shared_connection: Shared connection or interest (optional)

        Returns:
            EmailDraft with networking email content
        """
        # Generate email
        prompt = NETWORKING_USER.format(
            recipient_name=recipient_name,
            recipient_role=recipient_role,
            company_name=company_name,
            your_background=your_background,
            why_reaching_out=why_reaching_out,
            shared_connection=shared_connection or "your work in the industry"
        )

        try:
            body = await self.llm.generate(
                system=NETWORKING_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7
            )
        except Exception as e:
            body = f"[Error generating email: {str(e)}]"

        subject = f"Connecting about {company_name}"

        # Store draft (not tied to a specific application)
        draft_record = GeneratedDraft(
            application_id=None,
            draft_type="email_networking",
            content=body,
            metadata={
                "subject": subject,
                "recipient": recipient_name,
                "recipient_role": recipient_role,
                "company_name": company_name,
                "user_id": str(user_id)
            }
        )
        self.db.add(draft_record)
        await self.db.flush()

        return EmailDraft(
            draft_id=str(draft_record.id),
            email_type="networking",
            recipient=recipient_name,
            subject=subject,
            body=body,
            created_at=datetime.utcnow()
        )

    async def update_draft(
        self,
        draft_id: UUID,
        new_content: str,
        user_id: UUID
    ) -> EmailDraft:
        """
        Update an existing email draft.

        Args:
            draft_id: Draft to update
            new_content: New email body content
            user_id: User who owns the draft

        Returns:
            Updated EmailDraft
        """
        result = await self.db.execute(
            select(GeneratedDraft).where(GeneratedDraft.id == draft_id)
        )
        draft = result.scalar_one_or_none()

        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        # Update content
        draft.content = new_content
        await self.db.flush()

        metadata = draft.retrieved_chunk_ids or {}

        return EmailDraft(
            draft_id=str(draft.id),
            email_type=draft.draft_type.replace("email_", ""),
            recipient=metadata.get("recipient"),
            subject=metadata.get("subject", "Draft"),
            body=new_content,
            created_at=datetime.utcnow()
        )


async def generate_follow_up_email(
    db: AsyncSession,
    application_id: UUID,
    user_id: UUID
) -> EmailDraft:
    """
    Convenience function to generate a follow-up email.

    Args:
        db: Database session
        application_id: Application to follow up on
        user_id: User who owns the application

    Returns:
        EmailDraft with follow-up content
    """
    tool = EmailDraftingTool(db)
    return await tool.generate_follow_up(application_id, user_id)


async def generate_thank_you_email(
    db: AsyncSession,
    application_id: UUID,
    user_id: UUID,
    interviewer_name: str,
    interview_date: str,
    topics_discussed: Optional[str] = None,
    what_excited_you: Optional[str] = None
) -> EmailDraft:
    """
    Convenience function to generate a thank-you email.

    Args:
        db: Database session
        application_id: Application associated with interview
        user_id: User who owns the application
        interviewer_name: Name of the interviewer
        interview_date: Date/time of interview
        topics_discussed: Key topics from the interview
        what_excited_you: What excited you about the role

    Returns:
        EmailDraft with thank-you content
    """
    tool = EmailDraftingTool(db)
    return await tool.generate_thank_you(
        application_id, user_id, interviewer_name,
        interview_date, topics_discussed, what_excited_you
    )


async def generate_networking_email(
    db: AsyncSession,
    recipient_name: str,
    recipient_role: str,
    company_name: str,
    user_id: UUID,
    your_background: str,
    why_reaching_out: str,
    shared_connection: Optional[str] = None
) -> EmailDraft:
    """
    Convenience function to generate a networking outreach email.

    Args:
        db: Database session
        recipient_name: Name of the person to reach out to
        recipient_role: Their role/title
        company_name: Their company
        user_id: User sending the outreach
        your_background: Brief summary of user's background
        why_reaching_out: Reason for reaching out
        shared_connection: Shared connection or interest

    Returns:
        EmailDraft with networking email content
    """
    tool = EmailDraftingTool(db)
    return await tool.generate_networking_outreach(
        recipient_name, recipient_role, company_name,
        user_id, your_background, why_reaching_out, shared_connection
    )

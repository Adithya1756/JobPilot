"""
Jobs API routes - CRUD operations for job descriptions.

Jobs are the core entity for the agent:
- User pastes a job description
- Agent retrieves relevant experience
- Agent generates tailored application materials
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, Job, Application, ApplicationStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


# Request/Response schemas
class JobCreate(BaseModel):
    company_name: str
    role_title: str
    job_description: str
    source_url: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    company_name: str
    role_title: str
    job_description: str
    source_url: Optional[str]
    created_at: str
    has_application: bool = False
    application_status: Optional[str] = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int


class ApplicationCreate(BaseModel):
    job_id: str
    status: str = "saved"
    notes: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: str
    job_id: str
    status: str
    applied_at: Optional[str]
    follow_up_date: Optional[str]
    notes: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class ApplicationListResponse(BaseModel):
    applications: List[ApplicationResponse]


# Job endpoints
@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new job entry.

    This is the first step in the application flow:
    1. User pastes job description
    2. System stores it
    3. Agent uses it to generate materials
    """
    job = Job(
        user_id=current_user.id,
        company_name=request.company_name,
        role_title=request.role_title,
        job_description=request.job_description,
        source_url=request.source_url
    )
    db.add(job)
    await db.flush()

    return JobResponse(
        id=str(job.id),
        company_name=job.company_name,
        role_title=job.role_title,
        job_description=job.job_description,
        source_url=job.source_url,
        created_at=job.created_at.isoformat(),
        has_application=False,
        application_status=None
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all jobs for the current user.

    Includes application status if a job has been applied to.
    """
    # Get total count
    count_query = select(func.count(Job.id)).where(Job.user_id == current_user.id)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get jobs with application info
    query = (
        select(Job, Application)
        .outerjoin(Application, Application.job_id == Job.id)
        .where(Job.user_id == current_user.id)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    jobs = []
    for job, application in rows:
        jobs.append(JobResponse(
            id=str(job.id),
            company_name=job.company_name,
            role_title=job.role_title,
            job_description=job.job_description,
            source_url=job.source_url,
            created_at=job.created_at.isoformat(),
            has_application=application is not None,
            application_status=application.status if application else None
        ))

    return JobListResponse(jobs=jobs, total=total)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific job by ID."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Check for application
    app_result = await db.execute(
        select(Application).where(Application.job_id == job_id)
    )
    application = app_result.scalar_one_or_none()

    return JobResponse(
        id=str(job.id),
        company_name=job.company_name,
        role_title=job.role_title,
        job_description=job.job_description,
        source_url=job.source_url,
        created_at=job.created_at.isoformat(),
        has_application=application is not None,
        application_status=application.status if application else None
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a job and its associated application."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    await db.delete(job)


# Application endpoints
@router.post("/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    request: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create an application for a job.

    This tracks the job in the Kanban board (saved → applied → interview → offer/rejected).
    """
    # Verify job exists and belongs to user
    job_result = await db.execute(
        select(Job).where(Job.id == request.job_id, Job.user_id == current_user.id)
    )
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Check if application already exists
    existing_result = await db.execute(
        select(Application).where(Application.job_id == request.job_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application already exists for this job"
        )

    # Validate status
    valid_statuses = ["saved", "applied", "interview", "offer", "rejected"]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    application = Application(
        user_id=current_user.id,
        job_id=request.job_id,
        status=request.status,
        notes=request.notes
    )

    if request.status == "applied":
        application.applied_at = datetime.utcnow()

    db.add(application)
    await db.flush()

    return ApplicationResponse(
        id=str(application.id),
        job_id=str(application.job_id),
        status=application.status,
        applied_at=application.applied_at.isoformat() if application.applied_at else None,
        follow_up_date=application.follow_up_date.isoformat() if application.follow_up_date else None,
        notes=application.notes,
        created_at=application.created_at.isoformat()
    )


@router.get("/applications", response_model=ApplicationListResponse)
async def list_applications(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all applications for the current user.

    Optionally filter by status (for Kanban columns).
    """
    query = (
        select(Application)
        .where(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
    )

    if status_filter:
        query = query.where(Application.status == status_filter)

    result = await db.execute(query)
    applications = result.scalars().all()

    return ApplicationListResponse(
        applications=[
            ApplicationResponse(
                id=str(app.id),
                job_id=str(app.job_id),
                status=app.status,
                applied_at=app.applied_at.isoformat() if app.applied_at else None,
                follow_up_date=app.follow_up_date.isoformat() if app.follow_up_date else None,
                notes=app.notes,
                created_at=app.created_at.isoformat()
            )
            for app in applications
        ]
    )


@router.patch("/applications/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: UUID,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    follow_up_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an application's status, notes, or follow-up date."""
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == current_user.id
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )

    if status:
        valid_statuses = ["saved", "applied", "interview", "offer", "rejected"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        application.status = status

        if status == "applied" and not application.applied_at:
            application.applied_at = datetime.utcnow()

    if notes is not None:
        application.notes = notes

    if follow_up_date:
        application.follow_up_date = datetime.fromisoformat(follow_up_date.replace("Z", "+00:00"))

    await db.flush()

    return ApplicationResponse(
        id=str(application.id),
        job_id=str(application.job_id),
        status=application.status,
        applied_at=application.applied_at.isoformat() if application.applied_at else None,
        follow_up_date=application.follow_up_date.isoformat() if application.follow_up_date else None,
        notes=application.notes,
        created_at=application.created_at.isoformat()
    )

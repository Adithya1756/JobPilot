"""
Integration tests for simplified JobPilot with Gemini-only stack.

Tests the full flow: signup -> upload -> chat -> cover letter generation.
"""
import pytest
from sqlalchemy import text
from uuid import UUID

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.security import create_access_token, hash_password
from app.core.database import AsyncSessionLocal
from app.models.user import User


async def _create_test_user(db, email="integ@example.com", password="testpass123"):
    """Create a test user directly in DB."""
    user = User(
        email=email,
        hashed_password=hash_password(password),
        name="Integ Test"
    )
    db.add(user)
    await db.flush()
    await db.commit()
    return user


async def _get_token(user_id: str) -> str:
    """Create a valid access token for the user."""
    return create_access_token({"sub": user_id})


@pytest.mark.asyncio
async def test_full_flow_no_api_key():
    """Test full flow gracefully handles missing GEMINI_API_KEY."""
    async with AsyncSessionLocal() as db:
        # Clean slate
        await db.execute(text("DELETE FROM users WHERE email='integ@example.com'"))
        await db.commit()

        user = await _create_test_user(db)
        token = await _get_token(str(user.id))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Upload document
            content = b"John Doe, Software Engineer. 5 years Python experience at Acme Corp. Built RAG systems."
            files = {"file": ("resume.txt", content, "text/plain")}
            data = {"doc_type": "resume"}
            resp = await client.post("/documents/upload", headers=headers, files=files, data=data)
            assert resp.status_code == 201, resp.text
            doc_id = resp.json()["id"]

            # 2. Chat (no API key -> graceful error message)
            chat_resp = await client.post(
                "/agent/chat",
                headers=headers,
                json={"message": "What is my Python experience?"}
            )
            assert chat_resp.status_code == 200, chat_resp.text
            chat_data = chat_resp.json()
            assert "response" in chat_data
            assert "retrieved_chunks" in chat_data

            # 3. Create a job
            job_data = {
                "company_name": "TestCo",
                "role_title": "Senior Engineer",
                "job_description": "Looking for Python expert with RAG experience."
            }
            job_resp = await client.post("/jobs", headers=headers, json=job_data)
            assert job_resp.status_code == 201, job_resp.text
            job_id = job_resp.json()["id"]

            # 4. Generate cover letter
            draft_resp = await client.post(
                "/agent/draft",
                headers=headers,
                json={"job_id": job_id}
            )
            assert draft_resp.status_code == 201, draft_resp.text
            draft_data = draft_resp.json()
            assert "draft_id" in draft_data
            assert "content" in draft_data
            assert "retrieved_chunks" in draft_data

            # 5. Get draft back
            draft_id = draft_data["draft_id"]
            get_resp = await client.get(f"/agent/drafts/{draft_id}", headers=headers)
            assert get_resp.status_code == 200, get_resp.text

            # 6. Chat history
            hist_resp = await client.get("/memory/chat/00000000-0000-0000-0000-000000000001", headers=headers)
            assert hist_resp.status_code == 200, hist_resp.text

        # Cleanup
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM users WHERE email='integ@example.com'"))
            await db.commit()

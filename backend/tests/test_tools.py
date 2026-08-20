"""
Agent tool tests for JobPilot.

Tests calendar tool (mock mode) and tool registry.
"""
import pytest
from datetime import datetime, timedelta

from app.agent.calendar_tool import CalendarTool, get_calendar_tool
from app.agent.tool_registry import get_tool_registry, ToolRegistry, ToolName


@pytest.mark.asyncio
async def test_calendar_mock_create_event():
    """Test mock calendar creates an event."""
    tool = CalendarTool(use_mock=True)
    start = datetime.utcnow() + timedelta(days=1)
    event = await tool.create_interview(
        company_name="Acme Corp",
        role_title="Senior Engineer",
        start_time=start,
        duration_minutes=60
    )
    assert event.id.startswith("mock_event_")
    assert "Acme Corp" in event.title
    assert event.event_type == "interview"


@pytest.mark.asyncio
async def test_calendar_mock_list_events():
    """Test mock calendar lists upcoming events."""
    tool = CalendarTool(use_mock=True)
    start = datetime.utcnow() + timedelta(days=2)
    await tool.create_interview(
        company_name="TestCo",
        role_title="Dev",
        start_time=start
    )
    events = await tool.list_upcoming_events(days_ahead=7)
    assert len(events) >= 1
    assert all(e.start_time >= datetime.utcnow() for e in events)


@pytest.mark.asyncio
async def test_calendar_mock_delete():
    """Test mock calendar deletes events."""
    tool = CalendarTool(use_mock=True)
    start = datetime.utcnow() + timedelta(days=1)
    event = await tool.create_interview(
        company_name="DelCo",
        role_title="Eng",
        start_time=start
    )
    result = await tool.delete_event(event.id)
    assert result is True
    events = await tool.list_upcoming_events()
    assert all(e.id != event.id for e in events)


def test_tool_registry_new_instance():
    """Test tool registry returns new instance each call."""
    registry1 = get_tool_registry()
    registry2 = get_tool_registry()
    assert isinstance(registry1, ToolRegistry)
    assert isinstance(registry2, ToolRegistry)
    # They are separate instances
    assert registry1 is not registry2


def test_tool_registry_definitions():
    """Test tool registry has tool definitions."""
    registry = get_tool_registry()
    definitions = registry.get_tool_definitions()
    assert isinstance(definitions, list)
    assert len(definitions) >= 1

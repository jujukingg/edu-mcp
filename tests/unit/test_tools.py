"""Unit tests for Pronote MCP Tools."""

import pytest
from mcp.server.fastmcp import FastMCP
from edu_mcp.tools import register_all_tools


@pytest.fixture
def test_server(mock_session_manager):
    server = FastMCP("test_server")
    register_all_tools(server, mock_session_manager)
    return server, mock_session_manager


@pytest.mark.asyncio
async def test_account_tools(test_server):
    server, session_manager = test_server
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "pronote_get_user_info" in tool_names
    assert "pronote_list_children" in tool_names
    assert "pronote_select_child" in tool_names
    assert "pronote_list_ents" in tool_names


@pytest.mark.asyncio
async def test_timetable_tool_registered(test_server):
    server, _ = test_server
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "pronote_get_timetable" in tool_names


@pytest.mark.asyncio
async def test_homework_tools_registered(test_server):
    server, _ = test_server
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "pronote_get_homework" in tool_names
    assert "pronote_set_homework_done" in tool_names


@pytest.mark.asyncio
async def test_grades_tools_registered(test_server):
    server, _ = test_server
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "pronote_get_grades" in tool_names
    assert "pronote_get_averages" in tool_names


@pytest.mark.asyncio
async def test_school_life_tools_registered(test_server):
    server, _ = test_server
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "pronote_get_absences" in tool_names
    assert "pronote_get_news" in tool_names
    assert "pronote_get_canteen_menu" in tool_names

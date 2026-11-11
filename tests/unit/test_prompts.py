"""Unit tests for Pronote MCP Prompts."""

import pytest
from mcp.server.fastmcp import FastMCP
from pronote_mcp.prompts import register_prompts


@pytest.fixture
def test_prompt_server(mock_session_manager):
    server = FastMCP("test_prompt_server")
    register_prompts(server, mock_session_manager)
    return server


@pytest.mark.asyncio
async def test_prompts_registration(test_prompt_server):
    prompts = await test_prompt_server.list_prompts()
    prompt_names = [p.name for p in prompts]
    assert "pronote_daily_briefing" in prompt_names
    assert "pronote_homework_planner" in prompt_names

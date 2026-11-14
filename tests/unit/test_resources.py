"""Unit tests for Pronote MCP Resources."""

import pytest
from mcp.server.fastmcp import FastMCP
from edu_mcp.resources import register_resources


@pytest.fixture
def test_resource_server(mock_session_manager):
    server = FastMCP("test_res_server")
    register_resources(server, mock_session_manager)
    return server


@pytest.mark.asyncio
async def test_resources_registration(test_resource_server):
    resources = await test_resource_server.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "pronote://student/profile" in uris
    assert "pronote://timetable/today" in uris
    assert "pronote://homework/pending" in uris
    assert "pronote://grades/overview" in uris

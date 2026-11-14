"""Unit tests for Server factory."""

import pytest
from edu_mcp.server import create_server


@pytest.mark.asyncio
async def test_create_server_with_settings(dummy_settings):
    server = create_server(dummy_settings)
    assert server.name == "Edu MCP"
    tools = await server.list_tools()
    assert len(tools) >= 12
    resources = await server.list_resources()
    assert len(resources) >= 4
    prompts = await server.list_prompts()
    assert len(prompts) >= 2

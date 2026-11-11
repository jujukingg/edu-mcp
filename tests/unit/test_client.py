"""Unit tests for PronoteSessionManager."""

import pytest
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.config import PronoteSettings


@pytest.mark.asyncio
async def test_session_manager_init(dummy_settings):
    mgr = PronoteSessionManager(dummy_settings)
    assert mgr.settings == dummy_settings
    assert mgr._client is None
    assert len(mgr._stable_uuid) > 0


def test_list_supported_ents():
    ents = PronoteSessionManager.list_supported_ents()
    assert isinstance(ents, list)
    assert len(ents) > 0


@pytest.mark.asyncio
async def test_get_children_empty_for_student(mock_session_manager):
    children = await mock_session_manager.get_children()
    assert children == []


@pytest.mark.asyncio
async def test_execute_on_target(mock_session_manager):
    res = await mock_session_manager.execute_on_target(lambda t: t.name)
    assert res == "Jean Dupont"

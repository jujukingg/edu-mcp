"""Live smoke test against real Pronote instance using credentials in .env."""

import asyncio
import datetime
import os
import sys

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from edu_mcp.config import PronoteSettings
from edu_mcp.client import PronoteSessionManager
from edu_mcp.server import create_server


async def main():
    print("=== Pronote MCP Live Smoke Test ===")
    settings = PronoteSettings()
    print(f"Target URL: {settings.url}")
    print(f"Username: {settings.username}")
    print(f"Account type: {settings.account_type}")

    session_mgr = PronoteSessionManager(settings)
    target = await session_mgr.get_active_target()
    user_info = getattr(target, "info", target)
    print(f"Successfully authenticated as: {getattr(user_info, 'name', 'Inconnu')}")

    today = datetime.date.today()
    lessons = await session_mgr.execute_on_target(lambda t: t.lessons(today))
    print(f"Lessons retrieved for today: {len(lessons)}")

    hw = await session_mgr.execute_on_target(lambda t: t.homework(today))
    print(f"Homework items retrieved: {len(hw)}")

    periods = getattr(target, "periods", [])
    print(f"Periods available: {len(periods)}")

    server = create_server(settings)
    tools = await server.list_tools()
    print(f"Server tools loaded: {len(tools)}")
    print("=== Smoke test PASSED successfully ===")


if __name__ == "__main__":
    asyncio.run(main())

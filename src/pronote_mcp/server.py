"""Pronote MCP Server initialization and startup."""

import logging
import sys
from typing import Optional

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from mcp.server.fastmcp import FastMCP
from pronote_mcp.config import PronoteSettings
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.tools import register_all_tools
from pronote_mcp.resources import register_resources
from pronote_mcp.prompts import register_prompts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("pronote_mcp.server")


def create_server(settings: Optional[PronoteSettings] = None) -> FastMCP:
    """Create and configure the Pronote MCP server instance."""
    if settings is None:
        settings = PronoteSettings()

    server = FastMCP(
        name="Pronote MCP",
        instructions="Antigravity Gemini MCP Server for Pronote integration",
    )
    session_manager = PronoteSessionManager(settings)

    register_all_tools(server, session_manager)
    register_resources(server, session_manager)
    register_prompts(server, session_manager)

    return server


def main() -> None:
    """Entry point for the MCP server running over stdio."""
    try:
        server = create_server()
        server.run("stdio")
    except Exception as exc:
        logger.exception("Pronote MCP Server encountered a fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

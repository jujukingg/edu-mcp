"""Pronote MCP Server initialization and startup."""

import logging
import sys
from typing import Optional

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import pronotepy
if hasattr(pronotepy, "pronoteAPI") and hasattr(pronotepy.pronoteAPI, "HEADERS_MOBILE"):
    pronotepy.pronoteAPI.HEADERS_MOBILE = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    }

from mcp.server.fastmcp import FastMCP
from edu_mcp.config import PronoteSettings, load_settings_or_none
from edu_mcp.client import PronoteSessionManager
from edu_mcp.tools import register_all_tools
from edu_mcp.resources import register_resources
from edu_mcp.prompts import register_prompts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("edu_mcp.server")


def create_server(settings: Optional[PronoteSettings] = None) -> FastMCP:
    """Create and configure the Pronote MCP server instance."""
    if settings is None:
        settings = load_settings_or_none()
        if settings is None:
            logger.info("No valid .env configuration found at startup; secure popup will be used on first request.")

    server = FastMCP(
        name="Edu MCP",
        instructions="Unified MCP Server for French school platforms (Pronote, ÉcoleDirecte, Skolengo, ENT)",
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

"""Tool registration for Pronote MCP Server."""

from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.tools.account import register_account_tools
from pronote_mcp.tools.timetable import register_timetable_tools
from pronote_mcp.tools.homework import register_homework_tools
from pronote_mcp.tools.grades import register_grades_tools
from pronote_mcp.tools.school_life import register_school_life_tools
from pronote_mcp.tools.messaging import register_messaging_tools
from pronote_mcp.tools.files import register_files_tools
from pronote_mcp.tools.academics import register_academics_tools
from pronote_mcp.tools.analytics import register_analytics_tools


def register_all_tools(server: FastMCP, session_manager: PronoteSessionManager) -> None:
    """Register all Pronote tools on the MCP server instance."""
    register_account_tools(server, session_manager)
    register_timetable_tools(server, session_manager)
    register_homework_tools(server, session_manager)
    register_grades_tools(server, session_manager)
    register_school_life_tools(server, session_manager)
    register_messaging_tools(server, session_manager)
    register_files_tools(server, session_manager)
    register_academics_tools(server, session_manager)
    register_analytics_tools(server, session_manager)

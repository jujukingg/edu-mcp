"""Tool registration for Pronote MCP Server."""

from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.tools.account import register_account_tools
from pronote_mcp.tools.timetable import register_timetable_tools
from pronote_mcp.tools.homework import register_homework_tools
from pronote_mcp.tools.grades import register_grades_tools
from pronote_mcp.tools.school_life import register_school_life_tools


def register_all_tools(server: FastMCP, session_manager: PronoteSessionManager) -> None:
    """Register all Pronote tools on the MCP server instance."""
    register_account_tools(server, session_manager)
    register_timetable_tools(server, session_manager)
    register_homework_tools(server, session_manager)
    register_grades_tools(server, session_manager)
    register_school_life_tools(server, session_manager)

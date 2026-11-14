"""Tool registration for Pronote MCP Server."""

from mcp.server.fastmcp import FastMCP
from edu_mcp.client import PronoteSessionManager
from edu_mcp.tools.account import register_account_tools
from edu_mcp.tools.timetable import register_timetable_tools
from edu_mcp.tools.homework import register_homework_tools
from edu_mcp.tools.grades import register_grades_tools
from edu_mcp.tools.school_life import register_school_life_tools
from edu_mcp.tools.messaging import register_messaging_tools
from edu_mcp.tools.files import register_files_tools
from edu_mcp.tools.academics import register_academics_tools
from edu_mcp.tools.analytics import register_analytics_tools
from edu_mcp.tools.edu_unified import register_edu_tools


def register_all_tools(server: FastMCP, session_manager: PronoteSessionManager) -> None:
    """Register all Pronote and unified multi-platform tools on the MCP server instance."""
    register_account_tools(server, session_manager)
    register_timetable_tools(server, session_manager)
    register_homework_tools(server, session_manager)
    register_grades_tools(server, session_manager)
    register_school_life_tools(server, session_manager)
    register_messaging_tools(server, session_manager)
    register_files_tools(server, session_manager)
    register_academics_tools(server, session_manager)
    register_analytics_tools(server, session_manager)
    register_edu_tools(server, session_manager)

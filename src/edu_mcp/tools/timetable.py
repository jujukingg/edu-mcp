"""Timetable and schedule tools for Pronote MCP Server."""

import datetime
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from edu_mcp.client import PronoteSessionManager
from edu_mcp.models import LessonDTO
from edu_mcp.utils import map_lesson


def register_timetable_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register timetable tools on the MCP server."""

    @server.tool(
        name="pronote_get_timetable",
        description="Get lessons, schedule, and pedagogical lesson content for a date range (defaults to today). Format: YYYY-MM-DD.",
    )
    async def pronote_get_timetable(
        date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        today = datetime.date.today()
        d_from = datetime.date.fromisoformat(date_from) if date_from else today
        d_to = datetime.date.fromisoformat(date_to) if date_to else d_from

        def _fetch_lessons(target: Any) -> List[LessonDTO]:
            raw_lessons = target.lessons(d_from, d_to)
            lessons = [map_lesson(lesson) for lesson in raw_lessons]
            return sorted(lessons, key=lambda l: l.start)

        res_dtos = await session_manager.execute_on_target(_fetch_lessons)
        return [l.model_dump() for l in res_dtos]

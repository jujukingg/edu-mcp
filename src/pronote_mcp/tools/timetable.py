"""Timetable and schedule tools for Pronote MCP Server."""

import datetime
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.models import LessonDTO


def register_timetable_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register timetable tools on the MCP server."""

    @server.tool(
        name="pronote_get_timetable",
        description="Get lessons and schedule for a date range (defaults to today). Format: YYYY-MM-DD.",
    )
    async def pronote_get_timetable(
        date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        today = datetime.date.today()
        d_from = datetime.date.fromisoformat(date_from) if date_from else today
        d_to = datetime.date.fromisoformat(date_to) if date_to else d_from

        def _fetch_lessons(target: Any) -> List[LessonDTO]:
            raw_lessons = target.lessons(d_from, d_to)
            lessons: List[LessonDTO] = []
            for lesson in raw_lessons:
                subject_name = getattr(lesson.subject, "name", str(lesson.subject or "Sans matière"))
                teacher_name = getattr(lesson.teacher, "name", str(lesson.teacher or "")) if getattr(lesson, "teacher", None) else None
                classroom_name = getattr(lesson.classroom, "name", str(lesson.classroom or "")) if getattr(lesson, "classroom", None) else None
                
                start_iso = lesson.start.isoformat() if hasattr(lesson.start, "isoformat") else str(lesson.start)
                end_iso = lesson.end.isoformat() if hasattr(lesson.end, "isoformat") else str(lesson.end)

                lessons.append(
                    LessonDTO(
                        id=str(getattr(lesson, "id", f"{start_iso}_{subject_name}")),
                        subject=subject_name,
                        teacher=teacher_name,
                        classroom=classroom_name,
                        start=start_iso,
                        end=end_iso,
                        status=str(getattr(lesson, "status", "normal")),
                        canceled=bool(getattr(lesson, "canceled", False)),
                        memo=getattr(lesson, "memo", None),
                    )
                )
            return sorted(lessons, key=lambda l: l.start)

        res_dtos = await session_manager.execute_on_target(_fetch_lessons)
        return [l.model_dump() for l in res_dtos]

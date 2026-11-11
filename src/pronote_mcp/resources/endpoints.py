"""Pronote MCP dynamic resources endpoints."""

import datetime
import json
from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.models import HomeworkDTO, LessonDTO, UserProfileDTO


def register_resources(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register all Pronote MCP resource endpoints."""

    @server.resource(
        "pronote://student/profile",
        name="Student Profile",
        description="Current Pronote student profile and metadata.",
        mime_type="application/json",
    )
    async def get_student_profile() -> str:
        target = await session_manager.get_active_target()
        info = getattr(target, "info", target)
        est = getattr(info, "establishment", getattr(target, "establishment", None))
        est_name = getattr(est, "name", str(est)) if est else None

        profile = UserProfileDTO(
            name=getattr(info, "name", getattr(target, "name", "Utilisateur Pronote")),
            student_class=getattr(info, "class_name", getattr(target, "class_name", None)),
            establishment=est_name,
            account_type=session_manager.settings.account_type,
            active_child=session_manager._active_child_name
            if session_manager.settings.account_type == "parent"
            else None,
        )
        return json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)

    @server.resource(
        "pronote://timetable/today",
        name="Today Timetable",
        description="Today's full schedule and lessons.",
        mime_type="application/json",
    )
    async def get_timetable_today() -> str:
        today = datetime.date.today()

        def _fetch_today(target):
            lessons = target.lessons(today, today)
            out = []
            for l in lessons:
                start_iso = l.start.isoformat() if hasattr(l.start, "isoformat") else str(l.start)
                end_iso = l.end.isoformat() if hasattr(l.end, "isoformat") else str(l.end)
                out.append(
                    LessonDTO(
                        id=str(getattr(l, "id", f"{start_iso}")),
                        subject=getattr(l.subject, "name", str(l.subject or "")),
                        teacher=getattr(l.teacher, "name", str(l.teacher or "")) if getattr(l, "teacher", None) else None,
                        classroom=getattr(l.classroom, "name", str(l.classroom or "")) if getattr(l, "classroom", None) else None,
                        start=start_iso,
                        end=end_iso,
                        status=str(getattr(l, "status", "normal")),
                        canceled=bool(getattr(l, "canceled", False)),
                        memo=getattr(l, "memo", None),
                    ).model_dump()
                )
            return sorted(out, key=lambda x: x["start"])

        lessons_data = await session_manager.execute_on_target(_fetch_today)
        return json.dumps(lessons_data, ensure_ascii=False, indent=2)

    @server.resource(
        "pronote://homework/pending",
        name="Pending Homework",
        description="Pending homework due in the next 14 days.",
        mime_type="application/json",
    )
    async def get_pending_homework() -> str:
        today = datetime.date.today()
        end_d = today + datetime.timedelta(days=14)

        def _fetch_pending(target):
            hw_list = target.homework(today, end_d)
            pending = []
            for h in hw_list:
                if not getattr(h, "done", False):
                    due_val = getattr(h, "date", getattr(h, "due_date", today))
                    due_str = due_val.isoformat() if hasattr(due_val, "isoformat") else str(due_val)
                    pending.append(
                        HomeworkDTO(
                            id=str(getattr(h, "id", "")),
                            subject=getattr(h.subject, "name", str(h.subject or "")),
                            description=getattr(h, "description", ""),
                            due_date=due_str,
                            done=False,
                        ).model_dump()
                    )
            return sorted(pending, key=lambda x: x["due_date"])

        hw_data = await session_manager.execute_on_target(_fetch_pending)
        return json.dumps(hw_data, ensure_ascii=False, indent=2)

    @server.resource(
        "pronote://grades/overview",
        name="Grades Overview",
        description="Summary of student and class averages across all periods.",
        mime_type="application/json",
    )
    async def get_grades_overview() -> str:
        def _fetch_overview(target):
            periods = getattr(target, "periods", [])
            out = []
            for p in periods:
                out.append(
                    {
                        "period": getattr(p, "name", "Période"),
                        "overall_average": str(getattr(p, "overall_average", "")),
                        "overall_class_average": str(
                            getattr(p, "class_overall_average", getattr(p, "class_average", ""))
                        ),
                        "grades_count": len(getattr(p, "grades", [])),
                    }
                )
            return out

        overview_data = await session_manager.execute_on_target(_fetch_overview)
        return json.dumps(overview_data, ensure_ascii=False, indent=2)

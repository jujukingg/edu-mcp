"""Pronote MCP dynamic resources endpoints."""

import datetime
import json
from mcp.server.fastmcp import FastMCP
from edu_mcp.client import PronoteSessionManager
from edu_mcp.models import DiscussionDTO, HomeworkDTO, UserProfileDTO
from edu_mcp.utils import map_lesson, to_iso


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
            out = [map_lesson(l).model_dump() for l in lessons]
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

    @server.resource(
        "pronote://messages/unread",
        name="Unread Discussions",
        description="List of unread Pronote discussion threads (read-only).",
        mime_type="application/json",
    )
    async def get_unread_messages() -> str:
        def _fetch_unread(target):
            if not hasattr(target, "discussions"):
                return []
            out = []
            for idx, d in enumerate(target.discussions(only_unread=True)):
                out.append(
                    DiscussionDTO(
                        id=str(getattr(d, "id", f"disc_unread_{idx}")),
                        subject=str(getattr(d, "subject", "Sans objet") or "Sans objet"),
                        creator=str(getattr(d, "creator", "")) if getattr(d, "creator", None) else None,
                        date=to_iso(getattr(d, "date", "")),
                        unread=True,
                        closed=bool(getattr(d, "closed", False)),
                    ).model_dump()
                )
            return out

        data = await session_manager.execute_on_target(_fetch_unread)
        return json.dumps(data, ensure_ascii=False, indent=2)

    @server.resource(
        "pronote://academics/weekly-radar",
        name="Weekly Radar",
        description="Summary of pending homework and canceled/modified lessons for the next 7 days.",
        mime_type="application/json",
    )
    async def get_weekly_radar_resource() -> str:
        today = datetime.date.today()
        end_d = today + datetime.timedelta(days=7)

        def _fetch_radar(target):
            pending_hw = [
                {
                    "id": str(getattr(h, "id", "")),
                    "subject": getattr(h.subject, "name", str(h.subject or "")),
                    "due_date": to_iso(getattr(h, "date", getattr(h, "due_date", today))),
                    "description": getattr(h, "description", ""),
                }
                for h in target.homework(today, end_d)
                if not getattr(h, "done", False)
            ]
            alerts = []
            for l in target.lessons(today, end_d):
                dto = map_lesson(l)
                status_l = dto.status.lower()
                if dto.canceled or any(kw in status_l for kw in ("annul", "modif", "remplac", "déplac", "chang")):
                    alerts.append(dto.model_dump())
            return {"pending_homework": pending_hw, "schedule_alerts": alerts}

        data = await session_manager.execute_on_target(_fetch_radar)
        return json.dumps(data, ensure_ascii=False, indent=2)

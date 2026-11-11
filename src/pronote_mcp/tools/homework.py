"""Homework tools for Pronote MCP Server."""

import datetime
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.models import HomeworkDTO, HomeworkFileDTO


def register_homework_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register homework tools on the MCP server."""

    @server.tool(
        name="pronote_get_homework",
        description="Get homework assignments for a given date range (default: next 14 days). Format: YYYY-MM-DD.",
    )
    async def pronote_get_homework(
        date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        today = datetime.date.today()
        d_from = datetime.date.fromisoformat(date_from) if date_from else today
        d_to = (
            datetime.date.fromisoformat(date_to)
            if date_to
            else today + datetime.timedelta(days=14)
        )

        def _fetch_homework(target: Any) -> List[HomeworkDTO]:
            raw_hw = target.homework(d_from, d_to)
            result: List[HomeworkDTO] = []
            for hw in raw_hw:
                files_dtos = []
                for f in getattr(hw, "files", []):
                    files_dtos.append(
                        HomeworkFileDTO(
                            name=getattr(f, "name", "Pièce jointe"),
                            url=getattr(f, "url", ""),
                        )
                    )

                due_d = getattr(hw, "date", getattr(hw, "due_date", today))
                due_str = due_d.isoformat() if hasattr(due_d, "isoformat") else str(due_d)
                subj = getattr(hw.subject, "name", str(hw.subject or "Sans matière"))

                result.append(
                    HomeworkDTO(
                        id=str(getattr(hw, "id", f"{due_str}_{subj}")),
                        subject=subj,
                        description=getattr(hw, "description", ""),
                        due_date=due_str,
                        done=bool(getattr(hw, "done", False)),
                        files=files_dtos,
                    )
                )
            return sorted(result, key=lambda h: h.due_date)

        res_dtos = await session_manager.execute_on_target(_fetch_homework)
        return [h.model_dump() for h in res_dtos]

    @server.tool(
        name="pronote_set_homework_done",
        description="Mark a homework assignment as done or not done using its ID.",
    )
    async def pronote_set_homework_done(homework_id: str, done: bool = True) -> str:
        def _update_homework(target: Any) -> bool:
            today = datetime.date.today()
            window_start = today - datetime.timedelta(days=14)
            window_end = today + datetime.timedelta(days=30)
            items = target.homework(window_start, window_end)
            for hw in items:
                if str(getattr(hw, "id", "")) == homework_id:
                    if hasattr(hw, "set_done"):
                        hw.set_done(done)
                        return True
            return False

        updated = await session_manager.execute_on_target(_update_homework)
        if updated:
            state = "fait" if done else "à faire"
            return f"Le devoir {homework_id} a été marqué comme {state}."
        return f"Devoir introuvable avec l'identifiant {homework_id} dans les 30 derniers/prochains jours."

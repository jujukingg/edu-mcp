"""Grades and averages tools for Pronote MCP Server."""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.models import GradeDTO, PeriodAveragesDTO, SubjectAverageDTO


def register_grades_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register grades and averages tools on the MCP server."""

    @server.tool(
        name="pronote_get_grades",
        description="Get individual grades and evaluations, optionally filtered by period name (e.g. 'Trimestre 1', 'Semestre 1').",
    )
    async def pronote_get_grades(
        period_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        def _fetch_grades(target: Any) -> List[GradeDTO]:
            results: List[GradeDTO] = []
            periods = getattr(target, "periods", [])
            for p in periods:
                p_name = getattr(p, "name", "Période inconnue")
                if period_name and period_name.lower() not in p_name.lower():
                    continue

                for g in getattr(p, "grades", []):
                    subj = getattr(g.subject, "name", str(g.subject or "Sans matière"))
                    date_val = getattr(g, "date", "")
                    date_str = date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val)

                    results.append(
                        GradeDTO(
                            id=str(getattr(g, "id", f"{date_str}_{subj}_{getattr(g, 'grade', '')}")),
                            subject=subj,
                            grade=str(getattr(g, "grade", "")),
                            out_of=str(getattr(g, "out_of", "20")),
                            coefficient=str(getattr(g, "coefficient", "1")),
                            class_average=str(getattr(g, "average", "")) if getattr(g, "average", None) is not None else None,
                            max=str(getattr(g, "max", "")) if getattr(g, "max", None) is not None else None,
                            min=str(getattr(g, "min", "")) if getattr(g, "min", None) is not None else None,
                            date=date_str,
                            period=p_name,
                            comment=getattr(g, "comment", None),
                        )
                    )
            return sorted(results, key=lambda g: g.date, reverse=True)

        res_dtos = await session_manager.execute_on_target(_fetch_grades)
        return [g.model_dump() for g in res_dtos]

    @server.tool(
        name="pronote_get_averages",
        description="Get student subject averages and overall class averages per school period.",
    )
    async def pronote_get_averages(
        period_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        def _fetch_averages(target: Any) -> List[PeriodAveragesDTO]:
            results: List[PeriodAveragesDTO] = []
            periods = getattr(target, "periods", [])
            for p in periods:
                p_name = getattr(p, "name", "Période")
                if period_name and period_name.lower() not in p_name.lower():
                    continue

                subj_dtos: List[SubjectAverageDTO] = []
                for avg in getattr(p, "averages", []):
                    subj = getattr(avg.subject, "name", str(avg.subject or "Sans matière"))
                    subj_dtos.append(
                        SubjectAverageDTO(
                            subject=subj,
                            student=str(getattr(avg, "student", "")) if getattr(avg, "student", None) is not None else None,
                            class_average=str(getattr(avg, "class_average", "")) if getattr(avg, "class_average", None) is not None else None,
                            max=str(getattr(avg, "max", "")) if getattr(avg, "max", None) is not None else None,
                            min=str(getattr(avg, "min", "")) if getattr(avg, "min", None) is not None else None,
                        )
                    )

                overall = getattr(p, "overall_average", None)
                class_overall = getattr(p, "class_overall_average", getattr(p, "class_average", None))

                results.append(
                    PeriodAveragesDTO(
                        period=p_name,
                        overall_average=str(overall) if overall is not None else None,
                        overall_class_average=str(class_overall) if class_overall is not None else None,
                        subjects=subj_dtos,
                    )
                )
            return results

        res_dtos = await session_manager.execute_on_target(_fetch_averages)
        return [a.model_dump() for a in res_dtos]

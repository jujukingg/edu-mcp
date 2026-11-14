"""Academic tools: competency evaluations, period reports, and teaching staff."""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.models import (
    AcquisitionDTO,
    EvaluationDTO,
    ReportDTO,
    ReportSubjectDTO,
    TeachingStaffDTO,
)
from pronote_mcp.utils import to_iso


def register_academics_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register competency evaluations, report card, and teaching staff tools."""

    @server.tool(
        name="pronote_get_evaluations",
        description="Get competency-based evaluations and acquisitions, optionally filtered by period name.",
    )
    async def pronote_get_evaluations(
        period_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        def _fetch_evaluations(target: Any) -> List[EvaluationDTO]:
            results: List[EvaluationDTO] = []
            for p in getattr(target, "periods", []):
                p_name = getattr(p, "name", "Période")
                if period_name and period_name.lower() not in p_name.lower():
                    continue
                for ev in getattr(p, "evaluations", []) or []:
                    subj = getattr(ev.subject, "name", str(ev.subject or "Sans matière"))
                    teacher_obj = getattr(ev, "teacher", None)
                    teacher_name = getattr(teacher_obj, "name", str(teacher_obj)) if teacher_obj else None
                    date_str = to_iso(getattr(ev, "date", ""))

                    acquisitions: List[AcquisitionDTO] = []
                    for acq in getattr(ev, "acquisitions", []) or []:
                        acquisitions.append(
                            AcquisitionDTO(
                                name=str(getattr(acq, "name", "")),
                                domain=getattr(acq, "domain", None),
                                pillar=getattr(acq, "pillar", None),
                                abbreviation=getattr(acq, "abbreviation", None),
                                level=str(getattr(acq, "level", "")),
                                coefficient=str(getattr(acq, "coefficient", "")) if getattr(acq, "coefficient", None) is not None else None,
                            )
                        )

                    results.append(
                        EvaluationDTO(
                            id=str(getattr(ev, "id", f"ev_{date_str}_{subj}")),
                            name=str(getattr(ev, "name", "Évaluation")),
                            subject=subj,
                            teacher=teacher_name,
                            date=date_str,
                            domain=getattr(ev, "domain", None),
                            description=getattr(ev, "description", None),
                            coefficient=str(getattr(ev, "coefficient", "")) if getattr(ev, "coefficient", None) is not None else None,
                            acquisitions=acquisitions,
                        )
                    )
            return sorted(results, key=lambda e: e.date, reverse=True)

        dtos = await session_manager.execute_on_target(_fetch_evaluations)
        return [e.model_dump() for e in dtos]

    @server.tool(
        name="pronote_get_report",
        description="Get period report card appreciations (overall and per subject), optionally filtered by period name.",
    )
    async def pronote_get_report(
        period_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        def _fetch_reports(target: Any) -> List[ReportDTO]:
            results: List[ReportDTO] = []
            for p in getattr(target, "periods", []):
                p_name = getattr(p, "name", "Période")
                if period_name and period_name.lower() not in p_name.lower():
                    continue
                rep = getattr(p, "report", None)
                if rep is None:
                    continue
                overall_comments = [str(c) for c in (getattr(rep, "comments", None) or []) if c]
                subj_dtos: List[ReportSubjectDTO] = []
                for rs in getattr(rep, "subjects", None) or []:
                    subj_obj = getattr(rs, "subject", None)
                    subj_name = getattr(subj_obj, "name", str(subj_obj or "Matière"))
                    comments = [str(c) for c in (getattr(rs, "comments", None) or []) if c]
                    subj_dtos.append(ReportSubjectDTO(subject=subj_name, comments=comments))
                results.append(
                    ReportDTO(
                        period=p_name,
                        overall_comments=overall_comments,
                        subjects=subj_dtos,
                    )
                )
            return results

        dtos = await session_manager.execute_on_target(_fetch_reports)
        return [r.model_dump() for r in dtos]

    @server.tool(
        name="pronote_get_teaching_staff",
        description="Get the list of teachers and educational staff with their assigned subjects.",
    )
    async def pronote_get_teaching_staff() -> List[Dict[str, Any]]:
        def _fetch_staff(target: Any) -> List[TeachingStaffDTO]:
            if not hasattr(target, "get_teaching_staff"):
                return []
            try:
                raw_staff = target.get_teaching_staff() or []
            except Exception:
                return []
            results: List[TeachingStaffDTO] = []
            for idx, staff in enumerate(raw_staff):
                subjects_raw = getattr(staff, "subjects", None) or []
                subj_names = [
                    str(getattr(s, "name", getattr(getattr(s, "subject", None), "name", s)))
                    for s in subjects_raw
                ]
                results.append(
                    TeachingStaffDTO(
                        id=str(getattr(staff, "id", f"staff_{idx}")),
                        name=str(getattr(staff, "name", "Enseignant")),
                        type=str(getattr(staff, "type", "")) if getattr(staff, "type", None) is not None else None,
                        subjects=subj_names,
                    )
                )
            return sorted(results, key=lambda s: s.name)

        dtos = await session_manager.execute_on_target(_fetch_staff)
        return [s.model_dump() for s in dtos]

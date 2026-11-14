"""Academic analytics tools: grade simulator, progression analysis, and weekly radar."""

import datetime
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.models import (
    GradeSimulationDTO,
    HomeworkDTO,
    HomeworkFileDTO,
    LessonDTO,
    ProgressionAnalysisDTO,
    SubjectProgressionDTO,
    WeeklyRadarDTO,
)
from pronote_mcp.utils import map_lesson, parse_fr_float, to_iso


def _select_period(target: Any, period_name: Optional[str] = None) -> Any:
    """Pick matching period by name or fallback to current_period / last period."""
    periods = list(getattr(target, "periods", []) or [])
    if not periods:
        raise ValueError("Aucune période scolaire disponible.")
    if period_name:
        needle = period_name.strip().lower()
        for p in periods:
            if needle in str(getattr(p, "name", "")).lower():
                return p
        raise ValueError(f"Période introuvable : '{period_name}'.")
    current = getattr(target, "current_period", None)
    return current if current is not None else periods[-1]


def _compute_subject_average_from_grades(period: Any, subject_needle: str) -> Optional[tuple[float, float]]:
    """Return (weighted_sum_on_20, total_coeff) for grades matching subject_needle."""
    weighted_sum = 0.0
    total_coeff = 0.0
    for g in getattr(period, "grades", []) or []:
        subj_name = str(getattr(g.subject, "name", getattr(g, "subject", ""))).strip()
        if subject_needle not in subj_name.lower():
            continue
        val = parse_fr_float(getattr(g, "grade", None))
        out_of = parse_fr_float(getattr(g, "out_of", 20))
        coeff = parse_fr_float(getattr(g, "coefficient", 1))
        if val is None or out_of is None or out_of <= 0 or coeff is None or coeff <= 0:
            continue
        weighted_sum += (val / out_of) * 20.0 * coeff
        total_coeff += coeff
    if total_coeff == 0.0:
        return None
    return weighted_sum, total_coeff


def _period_averages_map(period: Any) -> Dict[str, tuple[Optional[float], Optional[float]]]:
    """Return {subject_lower: (student_avg, class_avg)} for a period."""
    mapping: Dict[str, tuple[Optional[float], Optional[float]]] = {}
    for avg in getattr(period, "averages", []) or []:
        subj_name = str(getattr(avg.subject, "name", getattr(avg, "subject", ""))).strip()
        if not subj_name:
            continue
        mapping[subj_name] = (
            parse_fr_float(getattr(avg, "student", None)),
            parse_fr_float(getattr(avg, "class_average", None)),
        )
    return mapping


def register_analytics_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register analytical and statistical tools on the MCP server."""

    @server.tool(
        name="pronote_simulate_grade",
        description=(
            "Simulate the exact impact of a hypothetical grade on a subject's average and overall average "
            "for the active (or specified) period."
        ),
    )
    async def pronote_simulate_grade(
        subject: str,
        hypothetical_grade: float,
        out_of: float = 20.0,
        coefficient: float = 1.0,
        period_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if out_of <= 0:
            raise ValueError("Le barème (out_of) doit être strictement positif.")
        if coefficient <= 0:
            raise ValueError("Le coefficient doit être strictement positif.")
        if hypothetical_grade < 0:
            raise ValueError("La note simulée ne peut pas être négative.")

        norm_grade = (hypothetical_grade / out_of) * 20.0
        needle = subject.strip().lower()

        def _simulate(target: Any) -> GradeSimulationDTO:
            period = _select_period(target, period_name)
            p_name = str(getattr(period, "name", "Période"))
            grade_stats = _compute_subject_average_from_grades(period, needle)
            avg_map = _period_averages_map(period)

            matched_subj = next((s for s in avg_map if needle in s.lower()), subject)
            if grade_stats is not None:
                w_sum, tot_c = grade_stats
                curr_subj_avg: Optional[float] = round(w_sum / tot_c, 2)
                sim_subj_avg = round((w_sum + norm_grade * coefficient) / (tot_c + coefficient), 2)
                notes = "Simulation calculée à partir des notes pondérées de la période."
            else:
                curr_subj_avg = avg_map.get(matched_subj, (None, None))[0]
                if curr_subj_avg is not None:
                    sim_subj_avg = round((curr_subj_avg + norm_grade * coefficient) / (1.0 + coefficient), 2)
                    notes = "Aucune note individuelle trouvée ; simulation approximée depuis la moyenne de matière (poids 1)."
                else:
                    sim_subj_avg = round(norm_grade, 2)
                    notes = "Aucune note existante dans cette matière ; la note simulée devient la moyenne."

            subj_delta = round(sim_subj_avg - curr_subj_avg, 2) if curr_subj_avg is not None else None

            valid_avgs = [v[0] for k, v in avg_map.items() if v[0] is not None and k != matched_subj]
            curr_overall = parse_fr_float(getattr(period, "overall_average", None))
            if curr_overall is not None and curr_subj_avg is not None and avg_map:
                subject_count = max(len([v for v in avg_map.values() if v[0] is not None]), 1)
                sim_overall = round(curr_overall + (sim_subj_avg - curr_subj_avg) / subject_count, 2)
            else:
                if curr_overall is None and avg_map:
                    all_vals = [v[0] for v in avg_map.values() if v[0] is not None]
                    curr_overall = round(sum(all_vals) / len(all_vals), 2) if all_vals else None
                sim_all = valid_avgs + [sim_subj_avg]
                sim_overall = round(sum(sim_all) / len(sim_all), 2) if sim_all else None
            overall_delta = (
                round(sim_overall - curr_overall, 2)
                if sim_overall is not None and curr_overall is not None
                else None
            )

            return GradeSimulationDTO(
                subject=matched_subj,
                period=p_name,
                current_subject_average=curr_subj_avg,
                simulated_subject_average=sim_subj_avg,
                subject_delta=subj_delta,
                current_overall_average=curr_overall,
                simulated_overall_average=sim_overall,
                overall_delta=overall_delta,
                notes=notes,
            )

        dto = await session_manager.execute_on_target(_simulate)
        return dto.model_dump()

    @server.tool(
        name="pronote_analyze_progression",
        description=(
            "Analyze academic progression between two school periods and compare student averages "
            "against class averages per subject."
        ),
    )
    async def pronote_analyze_progression(
        current_period_name: Optional[str] = None,
        previous_period_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        def _analyze(target: Any) -> ProgressionAnalysisDTO:
            periods = [p for p in getattr(target, "periods", []) or [] if getattr(p, "averages", None)]
            if not periods:
                periods = list(getattr(target, "periods", []) or [])
            if not periods:
                raise ValueError("Aucune période disponible pour l'analyse.")

            curr_p = _select_period(target, current_period_name) if current_period_name else periods[-1]
            if previous_period_name:
                prev_p: Optional[Any] = _select_period(target, previous_period_name)
            else:
                idx = periods.index(curr_p) if curr_p in periods else len(periods) - 1
                prev_p = periods[idx - 1] if idx > 0 else None

            curr_map = _period_averages_map(curr_p)
            prev_map = _period_averages_map(prev_p) if prev_p is not None else {}

            subjects: List[SubjectProgressionDTO] = []
            for subj_name, (curr_val, class_val) in sorted(curr_map.items()):
                prev_val = prev_map.get(subj_name, (None, None))[0]
                delta = round(curr_val - prev_val, 2) if curr_val is not None and prev_val is not None else None
                gap = round(curr_val - class_val, 2) if curr_val is not None and class_val is not None else None
                subjects.append(
                    SubjectProgressionDTO(
                        subject=subj_name,
                        previous_average=prev_val,
                        current_average=curr_val,
                        delta_period=delta,
                        class_average=class_val,
                        gap_vs_class=gap,
                    )
                )

            curr_overall = parse_fr_float(getattr(curr_p, "overall_average", None))
            prev_overall = parse_fr_float(getattr(prev_p, "overall_average", None)) if prev_p is not None else None
            overall_delta = (
                round(curr_overall - prev_overall, 2)
                if curr_overall is not None and prev_overall is not None
                else None
            )

            return ProgressionAnalysisDTO(
                previous_period=getattr(prev_p, "name", None) if prev_p is not None else None,
                current_period=str(getattr(curr_p, "name", "Période actuelle")),
                current_overall=curr_overall,
                previous_overall=prev_overall,
                overall_delta=overall_delta,
                subjects=subjects,
            )

        dto = await session_manager.execute_on_target(_analyze)
        return dto.model_dump()

    @server.tool(
        name="pronote_weekly_radar",
        description=(
            "Generate a weekly radar aggregating pending homework sorted by urgency, "
            "canceled/modified lessons, upcoming tests, and unread discussion count."
        ),
    )
    async def pronote_weekly_radar(days_ahead: int = 7) -> Dict[str, Any]:
        days = max(1, min(days_ahead, 30))
        today = datetime.date.today()
        end_date = today + datetime.timedelta(days=days)

        def _radar(target: Any) -> WeeklyRadarDTO:
            urgent_hw: List[HomeworkDTO] = []
            for hw in target.homework(today, end_date):
                if getattr(hw, "done", False):
                    continue
                due_d = getattr(hw, "date", getattr(hw, "due_date", today))
                due_str = to_iso(due_d)
                subj = getattr(hw.subject, "name", str(hw.subject or "Sans matière"))
                files_dtos = [
                    HomeworkFileDTO(name=getattr(f, "name", "Pièce jointe"), url=getattr(f, "url", ""))
                    for f in getattr(hw, "files", []) or []
                ]
                urgent_hw.append(
                    HomeworkDTO(
                        id=str(getattr(hw, "id", f"{due_str}_{subj}")),
                        subject=subj,
                        description=getattr(hw, "description", ""),
                        due_date=due_str,
                        done=False,
                        files=files_dtos,
                    )
                )
            urgent_hw.sort(key=lambda h: h.due_date)

            canceled_or_modified: List[LessonDTO] = []
            upcoming_tests: List[LessonDTO] = []
            for raw_lesson in target.lessons(today, end_date):
                dto = map_lesson(raw_lesson)
                status_l = dto.status.lower()
                is_canceled = dto.canceled or "annul" in status_l
                is_modified = any(kw in status_l for kw in ("modif", "remplac", "déplac", "chang"))
                if is_canceled or is_modified:
                    canceled_or_modified.append(dto)
                is_test = bool(getattr(raw_lesson, "test", False)) or any(
                    kw in status_l
                    for kw in ("bac blanc", "devoir", "contrôle", "controle", "examen", "épreuve", "epreuve", "partiel", "ds")
                )
                if is_test and not is_canceled:
                    upcoming_tests.append(dto)

            unread_count = 0
            if hasattr(target, "discussions"):
                try:
                    unread_count = len(target.discussions(only_unread=True))
                except Exception:
                    unread_count = 0

            return WeeklyRadarDTO(
                period_from=today.isoformat(),
                period_to=end_date.isoformat(),
                urgent_homework=urgent_hw,
                canceled_or_modified_lessons=sorted(canceled_or_modified, key=lambda l: l.start),
                upcoming_tests=sorted(upcoming_tests, key=lambda l: l.start),
                unread_discussions_count=unread_count,
            )

        dto = await session_manager.execute_on_target(_radar)
        return dto.model_dump()

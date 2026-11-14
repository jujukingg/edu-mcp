"""ÉcoleDirecte provider built on ecoledirecte-py-client."""

from datetime import date
import logging
from typing import Any, Dict, List, Optional

from edu_mcp.config import PronoteSettings, save_env_config
from edu_mcp.models import (
    AbsenceDTO,
    ChildDTO,
    DelayDTO,
    DiscussionDTO,
    MessageDTO,
    GradeDTO,
    HomeworkDTO,
    LessonDTO,
    NewsItemDTO,
    PeriodAveragesDTO,
    SubjectAverageDTO,
    UserProfileDTO,
)

logger = logging.getLogger("edu_mcp.providers.ecoledirecte")


def _strip_b64_html(raw: str) -> str:
    """Decode base64 HTML/text returned by some ÉcoleDirecte endpoints safely."""
    if not raw:
        return ""
    import base64
    import re

    try:
        decoded = base64.b64decode(raw, validate=True).decode("utf-8", errors="replace")
    except Exception:
        decoded = raw
    return re.sub(r"<[^>]+>", " ", decoded).strip()


class EcoleDirecteProvider:
    """Async provider for ÉcoleDirecte student and family accounts."""

    platform_name = "ecoledirecte"

    def __init__(self, settings: PronoteSettings) -> None:
        self.settings = settings
        self._client: Optional[Any] = None
        self._account: Optional[Any] = None
        self._active_student_idx: int = 0

    async def _ensure_connected(self) -> tuple[Any, Any]:
        """Authenticate with ÉcoleDirecte and return (client, active_student)."""
        if self._client is not None and self._account is not None:
            return self._client, self._active_student()

        from ecoledirecte_py_client import Client, Family, MFARequiredError

        username = self.settings.username or ""
        password = self.settings.password.get_secret_value() if self.settings.password else ""
        cn = self.settings.ed_cn.get_secret_value() if self.settings.ed_cn else None
        cv = self.settings.ed_cv.get_secret_value() if self.settings.ed_cv else None

        client = Client()
        try:
            account = await client.login(username, password, cn=cn, cv=cv)
        except MFARequiredError as exc:
            await client.close()
            raise ConnectionError(
                f"ÉcoleDirecte demande une validation QCM 2FA ({exc}). "
                "Relancez edu_setup_account avec platform='ecoledirecte' pour valider la question."
            ) from exc

        if isinstance(account, Family):
            await account.fetch()
        self._client = client
        self._account = account

        if getattr(account, "cn", None) and getattr(account, "cv", None):
            try:
                save_env_config({"EDU_ED_CN": str(account.cn), "EDU_ED_CV": str(account.cv)})
            except OSError:
                pass

        if self.settings.child_name:
            self._select_child_sync(self.settings.child_name)
        return client, self._active_student()

    def _students(self) -> List[Any]:
        if self._account is None:
            return []
        students = getattr(self._account, "students", None)
        if students:
            return list(students)
        return [self._account]

    def _active_student(self) -> Any:
        students = self._students()
        if not students:
            raise ConnectionError("Aucun profil élève trouvé sur ce compte ÉcoleDirecte.")
        idx = min(self._active_student_idx, len(students) - 1)
        return students[idx]

    def _select_child_sync(self, child_name: str) -> ChildDTO:
        target = child_name.strip().lower()
        for idx, stu in enumerate(self._students()):
            full_name = f"{getattr(stu, 'first_name', '')} {getattr(stu, 'last_name', '')}".strip()
            if target in full_name.lower():
                self._active_student_idx = idx
                return ChildDTO(name=full_name, student_class=getattr(stu, "class_name", None))
        raise ValueError(f"Élève '{child_name}' introuvable sur ce compte ÉcoleDirecte.")

    async def get_user_info(self) -> UserProfileDTO:
        _, stu = await self._ensure_connected()
        students = self._students()
        is_family = len(students) > 1 or getattr(self._account, "students", None) is not None
        full_name = f"{getattr(stu, 'first_name', '')} {getattr(stu, 'last_name', '')}".strip() or (
            self.settings.username or "Élève"
        )
        children = [
            ChildDTO(
                name=f"{getattr(s, 'first_name', '')} {getattr(s, 'last_name', '')}".strip(),
                student_class=getattr(s, "class_name", None),
            )
            for s in students
        ] if is_family else []
        return UserProfileDTO(
            name=full_name,
            student_class=getattr(stu, "class_name", None),
            establishment=getattr(stu, "school_name", None),
            account_type="parent" if is_family else "student",
            active_child=full_name if is_family else None,
            children=children,
        )

    async def list_children(self) -> List[ChildDTO]:
        await self._ensure_connected()
        return [
            ChildDTO(
                name=f"{getattr(s, 'first_name', '')} {getattr(s, 'last_name', '')}".strip(),
                student_class=getattr(s, "class_name", None),
            )
            for s in self._students()
        ]

    async def select_child(self, child_name: str) -> ChildDTO:
        await self._ensure_connected()
        return self._select_child_sync(child_name)

    async def get_timetable(self, start_date: date, end_date: date) -> List[LessonDTO]:
        _, stu = await self._ensure_connected()
        items = await stu.get_schedule(start_date=start_date, end_date=end_date)
        lessons: List[LessonDTO] = []
        for item in items or []:
            canceled = bool(getattr(item, "is_cancelled", False) or getattr(item, "canceled", False))
            lessons.append(
                LessonDTO(
                    id=str(getattr(item, "id", "")),
                    subject=str(getattr(item, "subject", None) or getattr(item, "text", "Cours")),
                    teacher=getattr(item, "teacher", None),
                    classroom=getattr(item, "room", None) or getattr(item, "classroom", None),
                    start=str(getattr(item, "start_date", "") or getattr(item, "start", "")),
                    end=str(getattr(item, "end_date", "") or getattr(item, "end", "")),
                    status="canceled" if canceled else "normal",
                    canceled=canceled,
                )
            )
        return lessons

    async def get_homework(self, start_date: date, end_date: date) -> List[HomeworkDTO]:
        _, stu = await self._ensure_connected()
        items = await stu.get_homework()
        result: List[HomeworkDTO] = []
        for hw in items or []:
            due = getattr(hw, "due_date", None) or getattr(hw, "date", "")
            due_str = due.isoformat() if hasattr(due, "isoformat") else str(due)
            if due_str and (due_str < start_date.isoformat() or due_str > end_date.isoformat()):
                continue
            result.append(
                HomeworkDTO(
                    id=str(getattr(hw, "id", "")),
                    subject=str(getattr(hw, "subject", "Devoir")),
                    description=_strip_b64_html(str(getattr(hw, "content", "") or getattr(hw, "description", ""))),
                    due_date=due_str,
                    done=bool(getattr(hw, "done", False)),
                )
            )
        return result

    async def set_homework_done(self, homework_id: str, done: bool = True) -> bool:
        client, stu = await self._ensure_connected()
        key = "idDevoirsEffectues" if done else "idDevoirsNonEffectues"
        payload = {key: [int(homework_id) if homework_id.isdigit() else homework_id]}
        await client.request(f"/eleves/{stu.id}/cahierdetexte.awp?verbe=put", payload)
        return True

    async def get_grades(self, period_name: Optional[str] = None) -> List[GradeDTO]:
        _, stu = await self._ensure_connected()
        data = await stu.get_grades()
        raw_grades = getattr(data, "grades", data) if not isinstance(data, list) else data
        grades: List[GradeDTO] = []
        for g in raw_grades or []:
            period = str(getattr(g, "period", "") or getattr(g, "code_periode", ""))
            if period_name and period_name.lower() not in period.lower():
                continue
            grades.append(
                GradeDTO(
                    id=str(getattr(g, "id", "")),
                    subject=str(getattr(g, "subject", "Matière")),
                    grade=str(getattr(g, "value", getattr(g, "grade", ""))),
                    out_of=str(getattr(g, "out_of", "20")),
                    coefficient=str(getattr(g, "coef", getattr(g, "coefficient", "1"))),
                    class_average=str(getattr(g, "class_average", "")) or None,
                    max=str(getattr(g, "max_average", "")) or None,
                    min=str(getattr(g, "min_average", "")) or None,
                    date=str(getattr(g, "date", "")),
                    period=period or "Période",
                    comment=getattr(g, "comment", None) or getattr(g, "title", None),
                )
            )
        return grades

    async def get_averages(self, period_name: Optional[str] = None) -> List[PeriodAveragesDTO]:
        _, stu = await self._ensure_connected()
        data = await stu.get_grades()
        periods = getattr(data, "periods", []) if not isinstance(data, list) else []
        results: List[PeriodAveragesDTO] = []
        for p in periods or []:
            p_name = str(getattr(p, "name", getattr(p, "period", "Période")))
            if period_name and period_name.lower() not in p_name.lower():
                continue
            subjects = [
                SubjectAverageDTO(
                    subject=str(getattr(s, "name", getattr(s, "subject", ""))),
                    student=str(getattr(s, "average", getattr(s, "student", ""))) or None,
                    class_average=str(getattr(s, "class_average", "")) or None,
                    max=str(getattr(s, "max", "")) or None,
                    min=str(getattr(s, "min", "")) or None,
                )
                for s in getattr(p, "subjects", []) or []
            ]
            results.append(
                PeriodAveragesDTO(
                    period=p_name,
                    overall_average=str(getattr(p, "average", "")) or None,
                    overall_class_average=str(getattr(p, "class_average", "")) or None,
                    subjects=subjects,
                )
            )
        return results

    async def get_absences(self, period_name: Optional[str] = None) -> Dict[str, Any]:
        client, stu = await self._ensure_connected()
        resp = await client.request(f"/eleves/{stu.id}/viescolaire.awp?verbe=get", {})
        data = resp.get("data", {}) if isinstance(resp, dict) else {}
        absences: List[dict] = []
        delays: List[dict] = []
        for item in data.get("absencesRetards", []) or []:
            kind = str(item.get("typeElement", "")).lower()
            entry_id = str(item.get("id", ""))
            if "retard" in kind:
                delays.append(
                    DelayDTO(
                        id=entry_id,
                        date=str(item.get("date", "")),
                        minutes=int(item.get("duree", 0) or 0),
                        justified=bool(item.get("justifie", False)),
                        justification=item.get("motif"),
                    ).model_dump()
                )
            else:
                absences.append(
                    AbsenceDTO(
                        id=entry_id,
                        from_date=str(item.get("date", "")),
                        to_date=str(item.get("dateFin", item.get("date", ""))),
                        justified=bool(item.get("justifie", False)),
                        reasons=[item["motif"]] if item.get("motif") else [],
                    ).model_dump()
                )
        return {"absences": absences, "delays": delays, "punishments": []}

    async def get_news(self) -> List[NewsItemDTO]:
        return []

    async def get_discussions(self) -> List[DiscussionDTO]:
        _, stu = await self._ensure_connected()
        items = await stu.get_messages()
        return [
            DiscussionDTO(
                id=str(getattr(m, "id", "")),
                subject=str(getattr(m, "subject", "Message")),
                creator=getattr(m, "sender", None),
                unread=not bool(getattr(m, "read", True)),
                date=str(getattr(m, "date", "")) or None,
                messages_count=1,
            )
            for m in (items or [])
        ]

    async def get_discussion_messages(self, thread_id: str) -> List[MessageDTO]:
        client, stu = await self._ensure_connected()
        resp = await client.request(f"/eleves/{stu.id}/messages/{thread_id}.awp?verbe=get&mode=destinataire", {})
        data = resp.get("data", {}) if isinstance(resp, dict) else {}
        return [
            MessageDTO(
                id=str(data.get("id", thread_id)),
                author=str(data.get("from", {}).get("name", "")) or None,
                date=str(data.get("date", "")) or None,
                content=_strip_b64_html(str(data.get("content", ""))),
            )
        ]

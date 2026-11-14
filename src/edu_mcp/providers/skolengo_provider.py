"""Skolengo provider using OAuth2 PKCE tokens and Skolengo JSON:API."""

from datetime import date
import hashlib
import base64
import secrets
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from edu_mcp.config import PronoteSettings, save_env_config
from edu_mcp.models import (
    AbsenceDTO,
    ChildDTO,
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

SKOLENGO_API_BASE = "https://api.skolengo.com/api/v1/bff-sko-app"
SKOLENGO_CLIENT_ID = "ko-app"
SKOLENGO_REDIRECT_URI = "skoapp-prod://sign-in-callback"


def build_pkce_pair() -> tuple[str, str]:
    """Generate (code_verifier, code_challenge) for OAuth2 PKCE."""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


async def search_skolengo_schools(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search Skolengo schools by name or city via the public BFF API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{SKOLENGO_API_BASE}/schools",
            params={"filter[text]": query, "page[limit]": limit},
        )
        resp.raise_for_status()
        payload = resp.json()
    schools: List[Dict[str, Any]] = []
    for item in payload.get("data", []):
        attrs = item.get("attributes", {})
        schools.append(
            {
                "id": item.get("id", ""),
                "name": attrs.get("name", ""),
                "city": attrs.get("city", ""),
                "ems_code": attrs.get("emsCode", ""),
                "oidc_url": attrs.get("emsOIDCWellKnownUrl", ""),
            }
        )
    return schools


def build_skolengo_auth_url(authorization_endpoint: str, ems_code: str, code_challenge: str, state: str) -> str:
    """Build the OAuth2 authorization URL for Skolengo."""
    params = {
        "response_type": "code",
        "client_id": SKOLENGO_CLIENT_ID,
        "redirect_uri": SKOLENGO_REDIRECT_URI,
        "scope": "openid offline_access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "kc_idp_hint": ems_code,
    }
    return f"{authorization_endpoint}?{urlencode(params)}"


class SkolengoProvider:
    """Async provider for Skolengo (OAuth2 + JSON:API)."""

    platform_name = "skolengo"

    def __init__(self, settings: PronoteSettings) -> None:
        self.settings = settings
        self._access_token: Optional[str] = (
            settings.skolengo_token.get_secret_value() if settings.skolengo_token else None
        )
        self._user_id: Optional[str] = None
        self._active_child_id: Optional[str] = None

    def _headers(self) -> Dict[str, str]:
        if not self._access_token:
            raise ConnectionError("Jeton Skolengo manquant. Lancez edu_setup_account avec platform='skolengo'.")
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/vnd.api+json",
        }
        if self.settings.skolengo_school_id:
            headers["X-Skolengo-School-Id"] = self.settings.skolengo_school_id
        if self.settings.skolengo_ems_code:
            headers["X-Skolengo-Ems-Code"] = self.settings.skolengo_ems_code
        return headers

    async def _refresh_access_token(self) -> None:
        """Refresh the Skolengo OAuth2 access token using the stored refresh token."""
        refresh = (
            self.settings.skolengo_refresh_token.get_secret_value()
            if self.settings.skolengo_refresh_token
            else None
        )
        if not refresh or not self.settings.skolengo_oidc_url:
            raise ConnectionError("Session Skolengo expirée. Relancez edu_setup_account.")
        async with httpx.AsyncClient(timeout=15.0) as client:
            well_known = (await client.get(self.settings.skolengo_oidc_url)).json()
            token_url = well_known["token_endpoint"]
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": SKOLENGO_CLIENT_ID,
                    "refresh_token": refresh,
                },
            )
            resp.raise_for_status()
            tok = resp.json()
        self._access_token = tok["access_token"]
        updates = {"EDU_SKOLENGO_TOKEN": self._access_token}
        if tok.get("refresh_token"):
            updates["EDU_SKOLENGO_REFRESH_TOKEN"] = tok["refresh_token"]
        try:
            save_env_config(updates)
        except OSError:
            pass

    async def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{SKOLENGO_API_BASE}{path}", headers=self._headers(), params=params)
            if resp.status_code == 401 and self.settings.skolengo_refresh_token:
                await self._refresh_access_token()
                resp = await client.get(f"{SKOLENGO_API_BASE}{path}", headers=self._headers(), params=params)
            resp.raise_for_status()
            return resp.json()

    async def _ensure_user_id(self) -> str:
        if self._active_child_id:
            return self._active_child_id
        if self._user_id:
            return self._user_id
        info = await self._get_json("/users-info")
        data = info.get("data", {})
        self._user_id = str(data.get("id", ""))
        return self._user_id

    async def get_user_info(self) -> UserProfileDTO:
        info = await self._get_json("/users-info")
        data = info.get("data", {})
        attrs = data.get("attributes", {})
        self._user_id = str(data.get("id", ""))
        name = f"{attrs.get('firstName', '')} {attrs.get('lastName', '')}".strip() or "Utilisateur Skolengo"
        return UserProfileDTO(
            name=name,
            student_class=attrs.get("className"),
            establishment=attrs.get("schoolName"),
            account_type="parent" if "PARENT" in str(attrs.get("profile", "")).upper() else "student",
        )

    async def list_children(self) -> List[ChildDTO]:
        return []

    async def select_child(self, child_name: str) -> ChildDTO:
        raise ValueError(f"Sélection d'enfant '{child_name}' non disponible sur ce profil Skolengo.")

    async def get_timetable(self, start_date: date, end_date: date) -> List[LessonDTO]:
        uid = await self._ensure_user_id()
        payload = await self._get_json(
            "/agenda",
            params={
                "filter[student.id]": uid,
                "filter[date][GE]": start_date.isoformat(),
                "filter[date][LE]": end_date.isoformat(),
            },
        )
        lessons: List[LessonDTO] = []
        for item in payload.get("data", []):
            attrs = item.get("attributes", {})
            canceled = bool(attrs.get("canceled", False))
            lessons.append(
                LessonDTO(
                    id=str(item.get("id", "")),
                    subject=str(attrs.get("subject", {}).get("label", "Cours") if isinstance(attrs.get("subject"), dict) else attrs.get("title", "Cours")),
                    classroom=attrs.get("location"),
                    start=str(attrs.get("startDateTime", "")),
                    end=str(attrs.get("endDateTime", "")),
                    status="canceled" if canceled else "normal",
                    canceled=canceled,
                )
            )
        return lessons

    async def get_homework(self, start_date: date, end_date: date) -> List[HomeworkDTO]:
        uid = await self._ensure_user_id()
        payload = await self._get_json(
            "/homework-assignments",
            params={
                "filter[student.id]": uid,
                "filter[dueDate][GE]": start_date.isoformat(),
                "filter[dueDate][LE]": end_date.isoformat(),
            },
        )
        result: List[HomeworkDTO] = []
        for item in payload.get("data", []):
            attrs = item.get("attributes", {})
            result.append(
                HomeworkDTO(
                    id=str(item.get("id", "")),
                    subject=str(attrs.get("title", "Devoir")),
                    description=str(attrs.get("html", "") or attrs.get("description", "")),
                    due_date=str(attrs.get("dueDate", "")),
                    done=bool(attrs.get("done", False)),
                )
            )
        return result

    async def set_homework_done(self, homework_id: str, done: bool = True) -> bool:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(
                f"{SKOLENGO_API_BASE}/homework-assignments/{homework_id}",
                headers={**self._headers(), "Content-Type": "application/vnd.api+json"},
                json={"data": {"type": "homeworkAssignment", "id": homework_id, "attributes": {"done": done}}},
            )
            resp.raise_for_status()
        return True

    async def get_grades(self, period_name: Optional[str] = None) -> List[GradeDTO]:
        uid = await self._ensure_user_id()
        payload = await self._get_json("/evaluations", params={"filter[student.id]": uid})
        grades: List[GradeDTO] = []
        for item in payload.get("data", []):
            attrs = item.get("attributes", {})
            grades.append(
                GradeDTO(
                    id=str(item.get("id", "")),
                    subject=str(attrs.get("title", "Évaluation")),
                    grade=str(attrs.get("mark", "")),
                    out_of=str(attrs.get("scale", "20")),
                    coefficient=str(attrs.get("coefficient", "1")),
                    class_average=str(attrs.get("average", "")) or None,
                    date=str(attrs.get("dateTime", "")),
                    period=period_name or "Période",
                    comment=attrs.get("topic"),
                )
            )
        return grades

    async def get_averages(self, period_name: Optional[str] = None) -> List[PeriodAveragesDTO]:
        uid = await self._ensure_user_id()
        payload = await self._get_json("/evaluation-services", params={"filter[student.id]": uid})
        subjects = [
            SubjectAverageDTO(
                subject=str(item.get("attributes", {}).get("subjectLabel", "Matière")),
                student=str(item.get("attributes", {}).get("studentAverage", "")) or None,
                class_average=str(item.get("attributes", {}).get("classAverage", "")) or None,
            )
            for item in payload.get("data", [])
        ]
        return [PeriodAveragesDTO(period=period_name or "Période", subjects=subjects)] if subjects else []

    async def get_absences(self, period_name: Optional[str] = None) -> Dict[str, Any]:
        uid = await self._ensure_user_id()
        payload = await self._get_json("/absence-files", params={"filter[student.id]": uid})
        absences = [
            AbsenceDTO(
                id=str(item.get("id", "")),
                from_date=str(item.get("attributes", {}).get("startDateTime", "")),
                to_date=str(item.get("attributes", {}).get("endDateTime", "")),
                justified=bool(item.get("attributes", {}).get("currentState") == "JUSTIFIED"),
                reasons=[str(item.get("attributes", {}).get("reason", ""))] if item.get("attributes", {}).get("reason") else [],
            ).model_dump()
            for item in payload.get("data", [])
        ]
        return {"absences": absences, "delays": [], "punishments": []}

    async def get_news(self) -> List[NewsItemDTO]:
        payload = await self._get_json("/school-infos")
        return [
            NewsItemDTO(
                id=str(item.get("id", "")),
                title=str(item.get("attributes", {}).get("title", "")),
                content=str(item.get("attributes", {}).get("content", "")),
                date=str(item.get("attributes", {}).get("publicationDateTime", "")) or None,
            )
            for item in payload.get("data", [])
        ]

    async def get_discussions(self) -> List[DiscussionDTO]:
        return []

    async def get_discussion_messages(self, thread_id: str) -> List[MessageDTO]:
        return []

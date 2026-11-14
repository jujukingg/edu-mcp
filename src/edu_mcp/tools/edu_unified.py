"""Unified multi-platform `edu_*` MCP tools (Pronote, ÉcoleDirecte, Skolengo)."""

import asyncio
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from edu_mcp.client import PronoteSessionManager


def register_edu_tools(server: FastMCP, session_manager: PronoteSessionManager) -> None:
    """Register unified multi-platform `edu_*` tools on the MCP server."""

    async def _pronote_fallback(tool_name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        res = await server.call_tool(tool_name, args or {})
        if isinstance(res, tuple) and len(res) == 2 and isinstance(res[1], dict):
            return res[1].get("result", res[1])
        return res

    @server.tool(
        name="edu_list_platforms",
        description="List supported school platforms (pronote, ecoledirecte, skolengo) and optionally search Skolengo schools.",
    )
    async def edu_list_platforms(skolengo_query: str = "") -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "platforms": [
                {"id": "pronote", "name": "Pronote (+ ENT / Toutatice / MBN / Île-de-France)", "auth": "browser_sso"},
                {"id": "ecoledirecte", "name": "ÉcoleDirecte", "auth": "credentials_and_qcm_2fa"},
                {"id": "skolengo", "name": "Skolengo", "auth": "oauth2_pkce_browser"},
            ]
        }
        if skolengo_query.strip():
            from edu_mcp.providers.skolengo_provider import search_skolengo_schools
            info["skolengo_schools"] = await search_skolengo_schools(skolengo_query.strip())
        return info

    @server.tool(
        name="edu_setup_account",
        description=(
            "Configure any supported school platform (pronote, ecoledirecte, skolengo). "
            "Call with platform='pronote'|'ecoledirecte'|'skolengo' (or empty to see guided instructions)."
        ),
    )
    async def edu_setup_account(
        platform: str = "pronote",
        pronote_url: str = "",
        account_type: str = "student",
        device_name: str = "MCP Assistant",
        username: str = "",
        password: str = "",
        mfa_answer: str = "",
        skolengo_school_query: str = "",
        skolengo_school_id: str = "",
        skolengo_ems_code: str = "",
        skolengo_oidc_url: str = "",
        env_file: str = "",
    ) -> str:
        target_platform = platform.strip().lower() or "pronote"

        if target_platform == "pronote":
            if not pronote_url.strip():
                return (
                    "CONFIGURATION PRONOTE REQUISE :\n"
                    "Expliquez à l'utilisateur qu'il peut se connecter via le navigateur officiel (ENT + 2FA) "
                    "sans partager son mot de passe dans le chat, puis demandez-lui son URL Pronote "
                    "(ex: https://xxx.index-education.net/pronote/eleve.html) et s'il s'agit d'un compte élève ou parent."
                )
            return await _pronote_fallback(
                "pronote_setup_account",
                {
                    "pronote_url": pronote_url,
                    "account_type": account_type,
                    "device_name": device_name,
                    "env_file": env_file,
                },
            )

        if target_platform == "ecoledirecte":
            if not username.strip() or not password.strip():
                return (
                    "CONFIGURATION ÉCOLEDIRECTE REQUISE :\n"
                    "Demandez à l'utilisateur son identifiant et mot de passe ÉcoleDirecte "
                    "(ou configurez PRONOTE_USERNAME, PRONOTE_PASSWORD et EDU_PLATFORM=ecoledirecte dans ~/.edu_mcp/.env)."
                )
            res = await session_manager.configure_ecoledirecte(
                username=username.strip(),
                password=password,
                mfa_answer=mfa_answer,
                env_path=Path(env_file) if env_file.strip() else None,
            )
            if res.get("status") == "mfa_required":
                return f"VALIDATION 2FA ÉCOLEDIRECTE REQUISE :\n{res.get('question')}\nRappelez edu_setup_account avec mfa_answer."
            return f"Compte ÉcoleDirecte configuré et enregistré dans {res.get('env_file')}."

        if target_platform == "skolengo":
            from edu_mcp.browser_auth import authenticate_skolengo_via_browser
            from edu_mcp.providers.skolengo_provider import search_skolengo_schools

            if not (skolengo_school_id and skolengo_ems_code and skolengo_oidc_url):
                if skolengo_school_query.strip():
                    schools = await search_skolengo_schools(skolengo_school_query.strip())
                    return f"Établissements Skolengo trouvés : {schools}"
                return (
                    "CONFIGURATION SKOLENGO REQUISE :\n"
                    "Appelez edu_setup_account(platform='skolengo', skolengo_school_query='nom ou ville du lycée') "
                    "pour trouver l'établissement, puis fournissez skolengo_school_id, skolengo_ems_code et skolengo_oidc_url."
                )
            saved = await asyncio.to_thread(
                authenticate_skolengo_via_browser,
                school_id=skolengo_school_id,
                ems_code=skolengo_ems_code,
                oidc_url=skolengo_oidc_url,
                env_path=Path(env_file) if env_file.strip() else None,
            )
            session_manager.settings = saved
            session_manager._provider = None
            return "Compte Skolengo connecté via OAuth2 et enregistré avec succès."

        return f"Plateforme inconnue '{platform}'. Plateformes supportées : pronote, ecoledirecte, skolengo."

    @server.tool(name="edu_get_user_info", description="Get active user profile across Pronote, ÉcoleDirecte, or Skolengo.")
    async def edu_get_user_info() -> Dict[str, Any]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_get_user_info")
        return (await provider.get_user_info()).model_dump()

    @server.tool(name="edu_get_timetable", description="Get timetable lessons for a date range across platforms.")
    async def edu_get_timetable(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_get_timetable", {"start_date": start_date, "end_date": end_date})
        s_date = date.fromisoformat(start_date) if start_date else date.today()
        e_date = date.fromisoformat(end_date) if end_date else (s_date + timedelta(days=6))
        return [l.model_dump() for l in await provider.get_timetable(s_date, e_date)]

    @server.tool(name="edu_get_homework", description="Get homework assignments for a date range across platforms.")
    async def edu_get_homework(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_get_homework", {"start_date": start_date, "end_date": end_date})
        s_date = date.fromisoformat(start_date) if start_date else date.today()
        e_date = date.fromisoformat(end_date) if end_date else (s_date + timedelta(days=7))
        return [h.model_dump() for h in await provider.get_homework(s_date, e_date)]

    @server.tool(name="edu_set_homework_done", description="Mark a homework item as done or pending across platforms.")
    async def edu_set_homework_done(homework_id: str, done: bool = True) -> bool:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_set_homework_done", {"homework_id": homework_id, "done": done})
        return await provider.set_homework_done(homework_id, done)

    @server.tool(name="edu_get_grades", description="Get grades for a period across platforms.")
    async def edu_get_grades(period_name: Optional[str] = None) -> List[Dict[str, Any]]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_get_grades", {"period_name": period_name})
        return [g.model_dump() for g in await provider.get_grades(period_name)]

    @server.tool(name="edu_get_averages", description="Get subject and overall averages across platforms.")
    async def edu_get_averages(period_name: Optional[str] = None) -> List[Dict[str, Any]]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_get_averages", {"period_name": period_name})
        return [a.model_dump() for a in await provider.get_averages(period_name)]

    @server.tool(name="edu_get_absences", description="Get absences, delays, and punishments across platforms.")
    async def edu_get_absences(period_name: Optional[str] = None) -> Dict[str, Any]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_get_absences", {"period_name": period_name})
        return await provider.get_absences(period_name)

    @server.tool(name="edu_get_news", description="Get school news and announcements across platforms.")
    async def edu_get_news() -> List[Dict[str, Any]]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_get_news")
        return [n.model_dump() for n in await provider.get_news()]

    @server.tool(name="edu_get_discussions", description="List read-only messaging threads across platforms.")
    async def edu_get_discussions() -> List[Dict[str, Any]]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_get_discussions")
        return [d.model_dump() for d in await provider.get_discussions()]

    @server.tool(name="edu_get_discussion_messages", description="Read messages in a thread (read-only) across platforms.")
    async def edu_get_discussion_messages(thread_id: str) -> List[Dict[str, Any]]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_get_discussion_messages", {"thread_id": thread_id})
        return [m.model_dump() for m in await provider.get_discussion_messages(thread_id)]

    @server.tool(name="edu_list_children", description="List linked children for parent accounts across platforms.")
    async def edu_list_children() -> List[Dict[str, Any]]:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_list_children")
        return [c.model_dump() for c in await provider.list_children()]

    @server.tool(name="edu_select_child", description="Select active child for parent accounts across platforms.")
    async def edu_select_child(child_name: str) -> str:
        provider = await session_manager.get_provider()
        if provider is None:
            return await _pronote_fallback("pronote_select_child", {"child_name": child_name})
        child = await provider.select_child(child_name)
        return f"Enfant actif changé avec succès pour : {child.name}"

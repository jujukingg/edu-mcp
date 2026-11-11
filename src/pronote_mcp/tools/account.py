"""Account management and information tools for Pronote."""

from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.models import ChildDTO, UserProfileDTO


def register_account_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register account-related tools on the MCP server."""

    @server.tool(
        name="pronote_get_user_info",
        description="Get current Pronote profile info (name, class, establishment, account type).",
    )
    async def pronote_get_user_info() -> Dict[str, Any]:
        target = await session_manager.get_active_target()
        is_parent = session_manager.settings.account_type == "parent"

        raw_children = []
        if is_parent:
            raw_children = await session_manager.get_children()

        children_dtos = [
            ChildDTO(
                name=c["name"],
                student_class=c.get("class_name"),
                establishment=c.get("establishment"),
            )
            for c in raw_children
        ]

        info = getattr(target, "info", target)
        est = getattr(info, "establishment", getattr(target, "establishment", None))
        est_name = getattr(est, "name", str(est)) if est else None

        profile = UserProfileDTO(
            name=getattr(info, "name", getattr(target, "name", "Utilisateur Pronote")),
            student_class=getattr(info, "class_name", getattr(target, "class_name", None)),
            establishment=est_name,
            account_type=session_manager.settings.account_type,
            active_child=session_manager._active_child_name if is_parent else None,
            children=children_dtos,
        )
        return profile.model_dump()

    @server.tool(
        name="pronote_list_children",
        description="List linked children when connected with a parent account.",
    )
    async def pronote_list_children() -> List[Dict[str, Any]]:
        raw_children = await session_manager.get_children()
        return [
            ChildDTO(
                name=c["name"],
                student_class=c.get("class_name"),
                establishment=c.get("establishment"),
            ).model_dump()
            for c in raw_children
        ]

    @server.tool(
        name="pronote_select_child",
        description="Select the active child for subsequent operations (parent account only).",
    )
    async def pronote_select_child(child_name: str) -> str:
        success = await session_manager.select_child(child_name)
        if success:
            return f"Enfant actif changé avec succès pour : {child_name}"
        return f"Impossible de sélectionner l'enfant : {child_name}"

    @server.tool(
        name="pronote_list_ents",
        description="List all supported ENT (Espaces Numériques de Travail) identity providers.",
    )
    async def pronote_list_ents() -> List[str]:
        return PronoteSessionManager.list_supported_ents()

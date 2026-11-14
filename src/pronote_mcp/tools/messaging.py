"""Read-only messaging tools (discussions and messages) for Pronote MCP Server."""

import hashlib
from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.models import DiscussionDTO, MessageDTO
from pronote_mcp.utils import to_iso


def _discussion_id(discussion: Any) -> str:
    """Return a stable identifier for a pronotepy Discussion."""
    explicit_id = getattr(discussion, "id", None)
    if explicit_id:
        return str(explicit_id)
    subject = str(getattr(discussion, "subject", "") or "")
    date_str = to_iso(getattr(discussion, "date", ""))
    creator = str(getattr(discussion, "creator", "") or "")
    digest = hashlib.sha1(f"{date_str}|{creator}|{subject}".encode("utf-8")).hexdigest()[:12]
    return f"disc_{digest}"


def _participant_names(raw_participants: Any) -> List[str]:
    """Extract readable names from discussion participants (method or iterable)."""
    if callable(raw_participants):
        try:
            raw_participants = raw_participants()
        except Exception:
            return []
    if not raw_participants:
        return []
    names: List[str] = []
    for p in raw_participants:
        names.append(str(getattr(p, "name", p)))
    return names


def register_messaging_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register strictly read-only messaging tools on the MCP server."""

    @server.tool(
        name="pronote_get_discussions",
        description="List Pronote discussion threads (read-only). Set only_unread=True to filter unread threads.",
    )
    async def pronote_get_discussions(
        only_unread: bool = False,
    ) -> List[Dict[str, Any]]:
        def _fetch_discussions(target: Any) -> List[DiscussionDTO]:
            if not hasattr(target, "discussions"):
                return []
            raw_list = target.discussions(only_unread=only_unread)
            items: List[DiscussionDTO] = []
            for d in raw_list:
                labels_raw = getattr(d, "labels", None) or []
                items.append(
                    DiscussionDTO(
                        id=_discussion_id(d),
                        subject=str(getattr(d, "subject", "Sans objet") or "Sans objet"),
                        creator=str(getattr(d, "creator", "")) if getattr(d, "creator", None) else None,
                        date=to_iso(getattr(d, "date", "")),
                        unread=bool(getattr(d, "unread", False)),
                        closed=bool(getattr(d, "closed", False)),
                        participants=_participant_names(getattr(d, "participants", None)),
                        labels=[str(getattr(lbl, "name", lbl)) for lbl in labels_raw],
                    )
                )
            return sorted(items, key=lambda x: x.date, reverse=True)

        res_dtos = await session_manager.execute_on_target(_fetch_discussions)
        return [d.model_dump() for d in res_dtos]

    @server.tool(
        name="pronote_get_discussion_messages",
        description="Read all messages inside a specific Pronote discussion thread (read-only) using its discussion_id.",
    )
    async def pronote_get_discussion_messages(
        discussion_id: str,
    ) -> List[Dict[str, Any]]:
        def _fetch_messages(target: Any) -> List[MessageDTO]:
            if not hasattr(target, "discussions"):
                return []
            raw_list = target.discussions()
            matched = next((d for d in raw_list if _discussion_id(d) == discussion_id), None)
            if matched is None:
                raise ValueError(f"Discussion introuvable avec l'identifiant '{discussion_id}'.")

            raw_msgs = getattr(matched, "messages", None) or []
            messages: List[MessageDTO] = []
            for idx, m in enumerate(raw_msgs):
                author_obj = getattr(m, "author", None)
                author_name = getattr(author_obj, "name", str(author_obj)) if author_obj else None
                date_val = getattr(m, "date", getattr(m, "created", ""))
                messages.append(
                    MessageDTO(
                        id=str(getattr(m, "id", f"{discussion_id}_msg_{idx}")),
                        author=author_name,
                        content=str(getattr(m, "content", "") or ""),
                        date=to_iso(date_val),
                        seen=bool(getattr(m, "seen", True)),
                    )
                )
            return sorted(messages, key=lambda x: x.date)

        res_dtos = await session_manager.execute_on_target(_fetch_messages)
        return [m.model_dump() for m in res_dtos]

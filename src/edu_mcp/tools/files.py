"""Attachment download and schedule export tools for Pronote MCP Server."""

import datetime
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Optional
from mcp.server.fastmcp import FastMCP
from edu_mcp.client import PronoteSessionManager
from edu_mcp.models import DownloadedFileDTO


_UNSAFE_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_save_path(download_dir: Path, raw_name: str) -> Path:
    """Resolve a sanitized destination path guaranteed to stay inside download_dir."""
    if not raw_name or not raw_name.strip():
        raise ValueError("Nom de fichier invalide ou vide.")
    if ".." in Path(raw_name).parts:
        raise ValueError("Chemin de fichier non autorisé (traversal détecté).")

    base_name = Path(raw_name.replace("\\", "/")).name
    clean_name = _UNSAFE_CHARS_RE.sub("_", base_name).strip(" .")
    if not clean_name or clean_name in (".", ".."):
        raise ValueError("Nom de fichier invalide après assainissement.")

    root = download_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    candidate = (root / clean_name).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Chemin de destination hors du dossier de téléchargement.")
    return candidate


def _find_matching_attachment(
    files: Optional[Iterable[Any]],
    attachment_name: Optional[str],
) -> Optional[Any]:
    """Return the matching attachment by name (case-insensitive) or the first one."""
    file_list = list(files or [])
    if not file_list:
        return None
    if not attachment_name:
        return file_list[0]
    needle = attachment_name.strip().lower()
    for f in file_list:
        if str(getattr(f, "name", "")).strip().lower() == needle:
            return f
    for f in file_list:
        if needle in str(getattr(f, "name", "")).strip().lower():
            return f
    return None


def _save_pronote_attachment(attachment: Any, dest: Path) -> int:
    """Persist a pronotepy Attachment to dest and return its size in bytes."""
    if hasattr(attachment, "save"):
        attachment.save(str(dest))
        if dest.exists():
            return dest.stat().st_size
    data = getattr(attachment, "data", None)
    if isinstance(data, (bytes, bytearray)):
        dest.write_bytes(bytes(data))
        return len(data)
    raise RuntimeError(f"Impossible de sauvegarder la pièce jointe '{getattr(attachment, 'name', dest.name)}'.")


def register_files_tools(
    server: FastMCP, session_manager: PronoteSessionManager
) -> None:
    """Register attachment download and export tools on the MCP server."""

    @server.tool(
        name="pronote_download_attachment",
        description=(
            "Download an attachment from a homework, lesson, or news item into PRONOTE_DOWNLOAD_DIR. "
            "source_type must be 'homework', 'lesson', or 'news'."
        ),
    )
    async def pronote_download_attachment(
        source_type: Literal["homework", "lesson", "news"],
        source_id: str,
        attachment_name: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        today = datetime.date.today()
        d_from = datetime.date.fromisoformat(date_from) if date_from else today - datetime.timedelta(days=30)
        d_to = datetime.date.fromisoformat(date_to) if date_to else today + datetime.timedelta(days=30)
        settings = await session_manager.ensure_configured()
        download_dir = settings.resolved_download_dir

        def _download(target: Any) -> DownloadedFileDTO:
            attachment = None
            if source_type == "homework":
                for hw in target.homework(d_from, d_to):
                    if str(getattr(hw, "id", "")) == source_id:
                        attachment = _find_matching_attachment(getattr(hw, "files", None), attachment_name)
                        break
            elif source_type == "lesson":
                for lesson in target.lessons(d_from, d_to):
                    if str(getattr(lesson, "id", "")) == source_id:
                        content = getattr(lesson, "content", None)
                        attachment = _find_matching_attachment(
                            getattr(content, "files", None) if content else None,
                            attachment_name,
                        )
                        break
            elif source_type == "news" and hasattr(target, "information_and_surveys"):
                for info in target.information_and_surveys(d_from):
                    if str(getattr(info, "id", "")) == source_id:
                        raw_files = getattr(info, "attachments", getattr(info, "files", None))
                        attachment = _find_matching_attachment(raw_files, attachment_name)
                        break

            if attachment is None:
                raise ValueError(
                    f"Pièce jointe introuvable pour source_type='{source_type}', source_id='{source_id}'."
                )

            raw_name = str(getattr(attachment, "name", "") or f"{source_type}_{source_id}.bin")
            dest = safe_save_path(download_dir, raw_name)
            size = _save_pronote_attachment(attachment, dest)
            return DownloadedFileDTO(
                filename=dest.name,
                saved_path=str(dest),
                size_bytes=size,
                source_type=source_type,
            )

        dto = await session_manager.execute_on_target(_download)
        return dto.model_dump()

    @server.tool(
        name="pronote_export_ical",
        description="Export the student's Pronote timetable as an .ics (iCalendar) file inside PRONOTE_DOWNLOAD_DIR.",
    )
    async def pronote_export_ical(
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        settings = await session_manager.ensure_configured()
        download_dir = settings.resolved_download_dir
        target_name = filename or f"pronote_timetable_{datetime.date.today().isoformat()}.ics"
        if not target_name.lower().endswith(".ics"):
            target_name += ".ics"
        dest = safe_save_path(download_dir, target_name)

        def _export(target: Any) -> DownloadedFileDTO:
            if not hasattr(target, "export_ical"):
                raise RuntimeError("L'export iCal n'est pas supporté par ce compte.")
            ical_text = target.export_ical()
            if isinstance(ical_text, bytes):
                dest.write_bytes(ical_text)
                size = len(ical_text)
            else:
                encoded = str(ical_text).encode("utf-8")
                dest.write_bytes(encoded)
                size = len(encoded)
            return DownloadedFileDTO(
                filename=dest.name,
                saved_path=str(dest),
                size_bytes=size,
                source_type="ical_export",
            )

        dto = await session_manager.execute_on_target(_export)
        return dto.model_dump()

    @server.tool(
        name="pronote_export_timetable_pdf",
        description="Generate and save the weekly timetable as a PDF file inside PRONOTE_DOWNLOAD_DIR.",
    )
    async def pronote_export_timetable_pdf(
        day: Optional[str] = None,
        portrait: bool = False,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        settings = await session_manager.ensure_configured()
        download_dir = settings.resolved_download_dir
        target_day = datetime.date.fromisoformat(day) if day else datetime.date.today()
        target_name = filename or f"pronote_timetable_{target_day.isoformat()}.pdf"
        if not target_name.lower().endswith(".pdf"):
            target_name += ".pdf"
        dest = safe_save_path(download_dir, target_name)

        def _export_pdf(target: Any) -> DownloadedFileDTO:
            if not hasattr(target, "generate_timetable_pdf"):
                raise RuntimeError("L'export PDF n'est pas supporté par ce compte.")
            pdf_result = target.generate_timetable_pdf(day=target_day, portrait=portrait)
            if isinstance(pdf_result, (bytes, bytearray)):
                dest.write_bytes(bytes(pdf_result))
                size = len(pdf_result)
            elif isinstance(pdf_result, str) and pdf_result.startswith(("http://", "https://")):
                comm = getattr(target, "communication", None)
                session = getattr(comm, "session", None)
                if session is None:
                    raise RuntimeError("Session HTTP indisponible pour télécharger le PDF généré.")
                resp = session.get(pdf_result, timeout=session_manager.settings.timeout)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                size = len(resp.content)
            else:
                raise RuntimeError(f"Format de retour PDF inattendu : {type(pdf_result).__name__}")
            return DownloadedFileDTO(
                filename=dest.name,
                saved_path=str(dest),
                size_bytes=size,
                source_type="pdf_export",
            )

        dto = await session_manager.execute_on_target(_export_pdf)
        return dto.model_dump()

"""Shared mapping and parsing helpers for Pronote MCP."""

import re
from typing import Any, Iterable, List, Optional
from edu_mcp.models import AttachmentDTO, LessonContentDTO, LessonDTO


def to_iso(value: Any, default: str = "") -> str:
    """Convert a date or datetime object to an ISO-8601 string."""
    if value is None:
        return default
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def parse_fr_float(value: Any) -> Optional[float]:
    """Parse a Pronote numeric string (supporting French commas and special tags like Abs)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    match = re.match(r"^-?\d+(?:\.\d+)?$", text)
    if not match:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def map_attachments(
    raw_files: Optional[Iterable[Any]],
    source_type: str,
    source_id: str,
) -> List[AttachmentDTO]:
    """Convert Pronote attachment objects into AttachmentDTOs."""
    if not raw_files:
        return []
    attachments: List[AttachmentDTO] = []
    for f in raw_files:
        attachments.append(
            AttachmentDTO(
                id=str(getattr(f, "id", "") or ""),
                name=str(getattr(f, "name", "Pièce jointe") or "Pièce jointe"),
                url=str(getattr(f, "url", "") or ""),
                type=str(getattr(f, "type", "")) if getattr(f, "type", None) is not None else None,
                source_type=source_type,
                source_id=source_id,
            )
        )
    return attachments


def _extract_lesson_content(lesson: Any, lesson_id: str) -> Optional[LessonContentDTO]:
    """Safely extract LessonContent from a pronotepy Lesson."""
    try:
        raw_content = getattr(lesson, "content", None)
    except Exception:
        return None
    if raw_content is None:
        return None
    files = map_attachments(
        getattr(raw_content, "files", None),
        source_type="lesson",
        source_id=lesson_id,
    )
    return LessonContentDTO(
        title=getattr(raw_content, "title", None),
        description=getattr(raw_content, "description", None),
        category=getattr(raw_content, "category", None),
        files=files,
    )


def map_lesson(lesson: Any) -> LessonDTO:
    """Convert a pronotepy Lesson into a LessonDTO including pedagogical content."""
    subject_name = getattr(lesson.subject, "name", str(lesson.subject or "Sans matière"))
    teacher_obj = getattr(lesson, "teacher", None)
    if teacher_obj is None:
        teacher_obj = getattr(lesson, "teacher_name", None)
    teacher_name = getattr(teacher_obj, "name", str(teacher_obj)) if teacher_obj else None

    classroom_obj = getattr(lesson, "classroom", None)
    classroom_name = getattr(classroom_obj, "name", str(classroom_obj)) if classroom_obj else None

    start_iso = to_iso(getattr(lesson, "start", ""))
    end_iso = to_iso(getattr(lesson, "end", ""))
    lesson_id = str(getattr(lesson, "id", f"{start_iso}_{subject_name}"))

    virtual_raw = getattr(lesson, "virtual_classrooms", None) or []
    virtual_list = [str(v) for v in virtual_raw if v]

    return LessonDTO(
        id=lesson_id,
        subject=subject_name,
        teacher=teacher_name,
        classroom=classroom_name,
        start=start_iso,
        end=end_iso,
        status=str(getattr(lesson, "status", "normal") or "normal"),
        canceled=bool(getattr(lesson, "canceled", False)),
        memo=getattr(lesson, "memo", None),
        virtual_classrooms=virtual_list,
        content=_extract_lesson_content(lesson, lesson_id),
    )

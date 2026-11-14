"""Unit tests for messaging, files/exports, academics, analytics, and enriched timetable."""

import datetime
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from mcp.server.fastmcp import FastMCP
from pronote_mcp.config import PronoteSettings, load_settings_or_none, save_env_config
from pronote_mcp.client import PronoteSessionManager
from pronote_mcp.prompts import register_prompts
from pronote_mcp.resources import register_resources
from pronote_mcp.server import create_server
from pronote_mcp.tools import register_all_tools
from pronote_mcp.tools.files import safe_save_path
from pronote_mcp.utils import parse_fr_float


def _extract_json(result):
    """Parse FastMCP call_tool return payload into Python data."""
    if isinstance(result, tuple):
        content_list, structured = result
        if structured is not None:
            return structured.get("result", structured) if isinstance(structured, dict) else structured
        result = content_list
    if isinstance(result, list) and result and hasattr(result[0], "text"):
        texts = [json.loads(item.text) for item in result if getattr(item, "text", None)]
        return texts[0] if len(texts) == 1 else texts
    return result


@pytest.fixture
def rich_server(tmp_path):
    """Build a FastMCP server backed by a rich mock Pronote target."""
    settings = PronoteSettings(
        url="https://demo.pronote.local/eleve.html",
        username="eleve",
        password="secret",
        download_dir=str(tmp_path / "downloads"),
    )
    manager = PronoteSessionManager(settings)
    target = MagicMock()
    today = datetime.date.today()

    # Timetable + LessonContent (one valid, one raising error on .content)
    att_lesson = SimpleNamespace(id="att_l1", name="cours_chap1.pdf", url="https://p/l1.pdf", type="File", data=b"%PDF-1.4")
    lesson1 = SimpleNamespace(
        id="l1",
        subject=SimpleNamespace(name="Mathématiques"),
        teacher=SimpleNamespace(name="M. Euler"),
        classroom=SimpleNamespace(name="S101"),
        start=datetime.datetime.combine(today, datetime.time(8, 0)),
        end=datetime.datetime.combine(today, datetime.time(9, 0)),
        status="normal",
        canceled=False,
        normal=True,
        test=True,
        memo="DS Chapitre 1",
        virtual_classrooms=[],
        content=SimpleNamespace(
            title="Dérivation",
            description="Étude de fonctions",
            category="Cours",
            files=[att_lesson],
        ),
    )

    class BrokenLesson:
        id = "l2"
        subject = SimpleNamespace(name="Physique")
        teacher = SimpleNamespace(name="Mme Curie")
        classroom = SimpleNamespace(name="Labo 2")
        start = datetime.datetime.combine(today, datetime.time(10, 0))
        end = datetime.datetime.combine(today, datetime.time(11, 0))
        status = "Cours annulé"
        canceled = True
        normal = False
        test = False
        memo = None
        virtual_classrooms = []

        @property
        def content(self):
            raise RuntimeError("Lazy load failed")

    target.lessons.return_value = [lesson1, BrokenLesson()]

    # Homework
    att_hw = SimpleNamespace(id="att_hw1", name="dm_maths.pdf", url="https://p/dm.pdf", type="File", data=b"DM_DATA")
    hw1 = SimpleNamespace(
        id="hw1",
        subject=SimpleNamespace(name="Mathématiques"),
        description="Faire l'exercice 12",
        date=today + datetime.timedelta(days=2),
        done=False,
        files=[att_hw],
    )
    target.homework.return_value = [hw1]

    # News
    att_news = SimpleNamespace(id="att_n1", name="reglement.pdf", url="https://p/reg.pdf", type="File", data=b"REG")
    news1 = SimpleNamespace(
        id="news1",
        title="Rentrée",
        author="Proviseur",
        creation_date=today,
        content="Bienvenue",
        category="Vie scolaire",
        read=True,
        attachments=[att_news],
    )
    target.information_and_surveys.return_value = [news1]

    # Discussions (read-only)
    msg1 = SimpleNamespace(
        id="m1",
        author=SimpleNamespace(name="M. Euler"),
        content="Bonjour, voici les consignes.",
        date=datetime.datetime.combine(today, datetime.time(9, 30)),
        seen=False,
    )
    disc1 = SimpleNamespace(
        id="disc1",
        subject="Consignes DS",
        creator="M. Euler",
        date=datetime.datetime.combine(today, datetime.time(9, 30)),
        unread=True,
        closed=False,
        participants=[SimpleNamespace(name="M. Euler"), SimpleNamespace(name="Élève")],
        labels=[SimpleNamespace(name="Important")],
        messages=[msg1],
    )
    target.discussions.return_value = [disc1]

    # Periods: T1 and T2 (grades, averages, evaluations, report)
    p1 = SimpleNamespace(
        name="Trimestre 1",
        overall_average="13,5",
        class_overall_average="12,0",
        grades=[],
        averages=[
            SimpleNamespace(subject=SimpleNamespace(name="Mathématiques"), student="14,0", class_average="12,0", max="18", min="7"),
            SimpleNamespace(subject=SimpleNamespace(name="Français"), student="13,0", class_average="12,0", max="17", min="8"),
        ],
        evaluations=[],
        report=None,
    )
    p2 = SimpleNamespace(
        name="Trimestre 2",
        overall_average="14,5",
        class_overall_average="12,5",
        grades=[
            SimpleNamespace(id="g1", subject=SimpleNamespace(name="Mathématiques"), grade="16,0", out_of="20", coefficient="2", average="13", max="19", min="8", date=today, comment="Très bien"),
            SimpleNamespace(id="g2", subject=SimpleNamespace(name="Mathématiques"), grade="Abs", out_of="20", coefficient="1", average="13", max="19", min="8", date=today, comment=None),
        ],
        averages=[
            SimpleNamespace(subject=SimpleNamespace(name="Mathématiques"), student="16,0", class_average="13,0", max="19", min="8"),
            SimpleNamespace(subject=SimpleNamespace(name="Français"), student="13,0", class_average="12,0", max="17", min="8"),
        ],
        evaluations=[
            SimpleNamespace(
                id="ev1",
                name="Éval Compétences",
                subject=SimpleNamespace(name="Mathématiques"),
                teacher=SimpleNamespace(name="M. Euler"),
                date=today,
                domain="Calcul",
                description="Suites",
                coefficient="1",
                acquisitions=[
                    SimpleNamespace(name="Modéliser", domain="Maths", pillar="D1", abbreviation="TBM", level="Très bonne maîtrise", coefficient="1")
                ],
            )
        ],
        report=SimpleNamespace(
            comments=["Bon trimestre dans l'ensemble."],
            subjects=[SimpleNamespace(subject=SimpleNamespace(name="Mathématiques"), comments=["Très sérieux."])],
        ),
    )
    target.periods = [p1, p2]
    target.current_period = p2

    # Teaching staff & Exports
    target.get_teaching_staff.return_value = [
        SimpleNamespace(id="st1", name="M. Euler", type="Professeur", subjects=[SimpleNamespace(name="Mathématiques")])
    ]
    target.export_ical.return_value = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
    target.generate_timetable_pdf.return_value = b"%PDF-1.4\n%mock\n"

    async def _exec(fn, *args, **kwargs):
        return fn(target)

    async def _get_target():
        return target

    manager.execute_on_target = _exec
    manager.get_active_target = _get_target

    server = FastMCP("test_pronote")
    register_all_tools(server, manager)
    register_resources(server, manager)
    register_prompts(server, manager)
    return server, tmp_path


@pytest.mark.asyncio
async def test_messaging_is_strictly_read_only(rich_server):
    server, _ = rich_server
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "pronote_get_discussions" in tool_names
    assert "pronote_get_discussion_messages" in tool_names
    for forbidden in ("send", "reply", "new_discussion", "delete_message"):
        assert not any(forbidden in name for name in tool_names)

    discs = _extract_json(await server.call_tool("pronote_get_discussions", {"only_unread": True}))
    assert len(discs) == 1
    assert discs[0]["id"] == "disc1"
    assert discs[0]["unread"] is True

    msgs = _extract_json(await server.call_tool("pronote_get_discussion_messages", {"discussion_id": "disc1"}))
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Bonjour, voici les consignes."


@pytest.mark.asyncio
async def test_timetable_includes_content_and_handles_errors(rich_server):
    server, _ = rich_server
    lessons = _extract_json(await server.call_tool("pronote_get_timetable", {}))
    assert len(lessons) == 2
    assert lessons[0]["content"]["title"] == "Dérivation"
    assert len(lessons[0]["content"]["files"]) == 1
    assert lessons[1]["canceled"] is True
    assert lessons[1]["content"] is None


@pytest.mark.asyncio
async def test_files_download_exports_and_traversal_guard(rich_server):
    server, tmp_path = rich_server

    with pytest.raises(ValueError, match="traversal"):
        safe_save_path(tmp_path / "downloads", "../../etc/passwd")

    dl_hw = _extract_json(
        await server.call_tool("pronote_download_attachment", {"source_type": "homework", "source_id": "hw1"})
    )
    assert dl_hw["filename"] == "dm_maths.pdf"
    assert dl_hw["size_bytes"] == 7

    dl_ical = _extract_json(await server.call_tool("pronote_export_ical", {"filename": "edt"}))
    assert dl_ical["filename"] == "edt.ics"
    assert (tmp_path / "downloads" / "edt.ics").exists()

    dl_pdf = _extract_json(await server.call_tool("pronote_export_timetable_pdf", {"portrait": True}))
    assert dl_pdf["filename"].endswith(".pdf")
    assert dl_pdf["size_bytes"] > 0


@pytest.mark.asyncio
async def test_academics_evaluations_report_and_staff(rich_server):
    server, _ = rich_server
    evals = _extract_json(await server.call_tool("pronote_get_evaluations", {"period_name": "Trimestre 2"}))
    assert len(evals) == 1
    assert evals[0]["acquisitions"][0]["abbreviation"] == "TBM"

    reports = _extract_json(await server.call_tool("pronote_get_report", {}))
    assert len(reports) == 1
    assert reports[0]["period"] == "Trimestre 2"
    assert reports[0]["subjects"][0]["comments"] == ["Très sérieux."]

    staff = _extract_json(await server.call_tool("pronote_get_teaching_staff", {}))
    assert len(staff) == 1
    assert staff[0]["name"] == "M. Euler"


@pytest.mark.asyncio
async def test_analytics_tools_and_fr_float_parsing(rich_server):
    server, _ = rich_server
    assert parse_fr_float("14,75") == 14.75
    assert parse_fr_float("Abs") is None

    sim = _extract_json(
        await server.call_tool(
            "pronote_simulate_grade",
            {"subject": "Mathématiques", "hypothetical_grade": 10.0, "out_of": 20.0, "coefficient": 2.0},
        )
    )
    assert sim["current_subject_average"] == 16.0
    assert sim["simulated_subject_average"] == 13.0
    assert sim["subject_delta"] == -3.0

    prog = _extract_json(await server.call_tool("pronote_analyze_progression", {}))
    assert prog["current_period"] == "Trimestre 2"
    assert prog["previous_period"] == "Trimestre 1"
    assert prog["overall_delta"] == 1.0

    radar = _extract_json(await server.call_tool("pronote_weekly_radar", {"days_ahead": 7}))
    assert len(radar["urgent_homework"]) == 1
    assert len(radar["canceled_or_modified_lessons"]) == 1
    assert len(radar["upcoming_tests"]) == 1
    assert radar["unread_discussions_count"] == 1


@pytest.mark.asyncio
async def test_new_resources_and_prompts_registered(rich_server):
    server, _ = rich_server
    resources = await server.list_resources()
    uris = {str(r.uri) for r in resources}
    assert "pronote://messages/unread" in uris
    assert "pronote://academics/weekly-radar" in uris

    prompts = await server.list_prompts()
    prompt_names = {p.name for p in prompts}
    assert "pronote_period_review" in prompt_names


def test_save_env_config_and_lazy_settings(tmp_path):
    env_file = tmp_path / ".env"
    assert load_settings_or_none(env_file) is None

    save_env_config(
        {
            "PRONOTE_URL": "https://demo.pronote.local/eleve.html\nINJECTED=1",
            "PRONOTE_USERNAME": "alice",
            "PRONOTE_PASSWORD": "secret",
        },
        env_path=env_file,
    )
    loaded = load_settings_or_none(env_file)
    assert loaded is not None
    assert loaded.url == "https://demo.pronote.local/eleve.htmlINJECTED=1"
    assert loaded.username == "alice"
    assert loaded.password.get_secret_value() == "secret"


@pytest.mark.asyncio
async def test_unconfigured_server_starts_and_triggers_popup(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    monkeypatch.setattr("pronote_mcp.server.load_settings_or_none", lambda: None)
    server = create_server()
    tools = await server.list_tools()
    assert "pronote_setup_account" in {t.name for t in tools}

    new_settings = PronoteSettings(
        url="https://demo.pronote.local/eleve.html",
        username="bob",
        password="pwd",
    )
    monkeypatch.setattr(
        "pronote_mcp.client.open_setup_popup",
        lambda *args, **kwargs: new_settings,
    )
    mgr = PronoteSessionManager(None)
    monkeypatch.setattr("pronote_mcp.client.load_settings_or_none", lambda: None)
    resolved = await mgr.ensure_configured()
    assert resolved.username == "bob"

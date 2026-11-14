"""Unit tests for multi-platform providers (Pronote, ÉcoleDirecte, Skolengo) and unified edu_* tools."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from edu_mcp.config import PronoteSettings
from edu_mcp.providers.ecoledirecte_provider import EcoleDirecteProvider
from edu_mcp.providers.skolengo_provider import SkolengoProvider, build_pkce_pair, build_skolengo_auth_url
from edu_mcp.server import create_server


def test_config_supports_ecoledirecte_and_skolengo():
    ed_cfg = PronoteSettings(
        _env_file=None,
        platform="ecoledirecte",
        username="jdupont",
        password="secret",
    )
    assert ed_cfg.platform == "ecoledirecte"

    sko_cfg = PronoteSettings(
        _env_file=None,
        platform="skolengo",
        skolengo_token="tok_123",
        skolengo_school_id="sko_1",
    )
    assert sko_cfg.platform == "skolengo"


@pytest.mark.asyncio
async def test_edu_unified_tools_registered_and_list_platforms():
    server = create_server(
        PronoteSettings(
            _env_file=None,
            url="https://demo.pronote.local/eleve.html",
            username="alice",
            password="secret",
        )
    )
    tools = await server.list_tools()
    names = {t.name for t in tools}
    for expected in (
        "edu_list_platforms",
        "edu_setup_account",
        "edu_get_user_info",
        "edu_get_timetable",
        "edu_get_homework",
        "edu_set_homework_done",
        "edu_get_grades",
        "edu_get_averages",
        "edu_get_absences",
        "edu_get_news",
        "edu_get_discussions",
        "edu_get_discussion_messages",
        "edu_list_children",
        "edu_select_child",
    ):
        assert expected in names

    res = await server.call_tool("edu_list_platforms", {})
    payload = res[1] if isinstance(res, tuple) else res
    platforms = payload["platforms"] if "platforms" in payload else payload["result"]["platforms"]
    assert {p["id"] for p in platforms} == {"pronote", "ecoledirecte", "skolengo"}


@pytest.mark.asyncio
async def test_ecoledirecte_provider_mapping():
    cfg = PronoteSettings(_env_file=None, platform="ecoledirecte", username="jdupont", password="secret")
    provider = EcoleDirecteProvider(cfg)

    fake_student = SimpleNamespace(
        id=42,
        first_name="Julien",
        last_name="Dupont",
        class_name="T STI2D",
        school_name="Lycée Demo",
        get_schedule=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=1,
                    subject="Maths",
                    teacher="M. Martin",
                    room="B12",
                    start_date="2026-11-16 08:00",
                    end_date="2026-11-16 09:00",
                    is_cancelled=False,
                )
            ]
        ),
        get_homework=AsyncMock(
            return_value=[
                SimpleNamespace(id=10, subject="Maths", content="Ex 1 p 12", due_date="2026-11-17", done=False)
            ]
        ),
        get_grades=AsyncMock(
            return_value=SimpleNamespace(
                grades=[
                    SimpleNamespace(
                        id=100,
                        subject="Maths",
                        value="16",
                        out_of="20",
                        coef="1",
                        class_average="12.5",
                        date="2026-11-10",
                        period="Trimestre 1",
                        comment="DS1",
                    )
                ],
                periods=[],
            )
        ),
        get_messages=AsyncMock(return_value=[]),
    )
    fake_client = SimpleNamespace(request=AsyncMock(return_value={"data": {"absencesRetards": []}}))
    provider._client = fake_client
    provider._account = fake_student

    profile = await provider.get_user_info()
    assert profile.name == "Julien Dupont"
    assert profile.student_class == "T STI2D"

    lessons = await provider.get_timetable(date(2026, 11, 16), date(2026, 11, 17))
    assert len(lessons) == 1 and lessons[0].subject == "Maths"

    hw = await provider.get_homework(date(2026, 11, 16), date(2026, 11, 18))
    assert len(hw) == 1 and hw[0].description == "Ex 1 p 12"

    grades = await provider.get_grades()
    assert len(grades) == 1 and grades[0].grade == "16"

    abs_res = await provider.get_absences()
    assert abs_res == {"absences": [], "delays": [], "punishments": []}


@pytest.mark.asyncio
async def test_skolengo_provider_pkce_and_mapping(monkeypatch):
    verifier, challenge = build_pkce_pair()
    assert len(verifier) > 20 and "=" not in challenge
    auth_url = build_skolengo_auth_url("https://idp.example/auth", "toutatice", challenge, "st1")
    assert "kc_idp_hint=toutatice" in auth_url and "code_challenge_method=S256" in auth_url

    cfg = PronoteSettings(
        _env_file=None,
        platform="skolengo",
        skolengo_token="tok_abc",
        skolengo_school_id="sko_1",
        skolengo_ems_code="toutatice",
    )
    provider = SkolengoProvider(cfg)

    async def fake_get_json(path, params=None):
        if path == "/users-info":
            return {"data": {"id": "u1", "attributes": {"firstName": "Alice", "lastName": "Martin", "className": "1G2"}}}
        if path == "/agenda":
            return {"data": [{"id": "l1", "attributes": {"title": "Physique", "startDateTime": "2026-11-16T10:00:00", "endDateTime": "2026-11-16T11:00:00"}}]}
        if path == "/evaluations":
            return {"data": [{"id": "g1", "attributes": {"title": "Physique", "mark": 17, "scale": 20, "coefficient": 1, "dateTime": "2026-11-12"}}]}
        return {"data": []}

    monkeypatch.setattr(provider, "_get_json", fake_get_json)

    profile = await provider.get_user_info()
    assert profile.name == "Alice Martin"
    lessons = await provider.get_timetable(date(2026, 11, 16), date(2026, 11, 17))
    assert len(lessons) == 1 and lessons[0].subject == "Physique"
    grades = await provider.get_grades()
    assert len(grades) == 1 and grades[0].grade == "17"

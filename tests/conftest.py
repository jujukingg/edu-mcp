"""Pytest fixtures and test doubles for Pronote MCP Server."""

import datetime
from unittest.mock import MagicMock
import pytest
from edu_mcp.config import PronoteSettings
from edu_mcp.client import PronoteSessionManager


class DummySubject:
    def __init__(self, name="Mathématiques"):
        self.name = name


class DummyUser:
    def __init__(self, name="Professeur"):
        self.name = name


class DummyClassroom:
    def __init__(self, name="B204"):
        self.name = name


class DummyLesson:
    def __init__(self, id="lesson_1", subject="Mathématiques", start=None, end=None, canceled=False):
        self.id = id
        self.subject = DummySubject(subject)
        self.teacher = DummyUser("M. Dupont")
        self.classroom = DummyClassroom("B204")
        now = datetime.datetime.now()
        self.start = start or now
        self.end = end or (now + datetime.timedelta(hours=1))
        self.status = "normal"
        self.canceled = canceled
        self.memo = "Contrôle prévu"


class DummyHomework:
    def __init__(self, id="hw_1", subject="Histoire", description="Faire exercice 5", done=False):
        self.id = id
        self.subject = DummySubject(subject)
        self.description = description
        self.date = datetime.date.today() + datetime.timedelta(days=1)
        self.done = done
        self.files = []

    def set_done(self, done: bool):
        self.done = done


class DummyGrade:
    def __init__(self, grade="15", out_of="20", subject="Français"):
        self.id = "g_1"
        self.subject = DummySubject(subject)
        self.grade = grade
        self.out_of = out_of
        self.coefficient = "1"
        self.average = "12"
        self.max = "18"
        self.min = "8"
        self.date = datetime.date.today()
        self.comment = "Bon travail"


class DummyAverage:
    def __init__(self, subject="Français", student="14.5", class_avg="12.0"):
        self.subject = DummySubject(subject)
        self.student = student
        self.class_average = class_avg
        self.max = "18.0"
        self.min = "7.5"


class DummyAbsence:
    def __init__(self):
        self.id = "abs_1"
        self.from_date = datetime.datetime.now()
        self.to_date = datetime.datetime.now() + datetime.timedelta(hours=2)
        self.justified = True
        self.hours = "2h00"
        self.reasons = ["Rendez-vous médical"]


class DummyDelay:
    def __init__(self):
        self.id = "del_1"
        self.date = datetime.datetime.now()
        self.minutes = "10"
        self.justified = False
        self.reasons = ["Bus en retard"]


class DummyPunishment:
    def __init__(self):
        self.id = "pun_1"
        self.date = datetime.datetime.now()
        self.given_by = "CPE"
        self.reasons = ["Bavardages"]
        self.circumstances = "Pendant le cours"
        self.nature = "Retenue"
        self.duration = "1h"


class DummyPeriod:
    def __init__(self, name="Trimestre 1"):
        self.name = name
        self.overall_average = "14.2"
        self.class_overall_average = "12.8"
        self.grades = [DummyGrade()]
        self.averages = [DummyAverage()]
        self.absences = [DummyAbsence()]
        self.delays = [DummyDelay()]
        self.punishments = [DummyPunishment()]


class DummyEstablishment:
    def __init__(self, name="Lycée Test"):
        self.name = name


class DummyStudentClient:
    def __init__(self):
        self.logged_in = True
        self.name = "Jean Dupont"
        self.class_name = "Terminale Générale"
        self.establishment = DummyEstablishment()
        self.periods = [DummyPeriod()]

    def lessons(self, d_from, d_to):
        return [DummyLesson()]

    def homework(self, d_from, d_to):
        return [DummyHomework()]

    def information_and_surveys(self, d_from):
        return []

    def menus(self, d_from, d_to):
        return []

    def session_check(self):
        return True


@pytest.fixture
def dummy_settings():
    return PronoteSettings(
        url="https://demo.index-education.net/pronote/eleve.html",
        username="test_user",
        password="secret_password",
        account_pin="1234",
        device_name="Test Device",
        account_type="student",
        session_file=None,
    )


@pytest.fixture
def mock_session_manager(dummy_settings):
    mgr = PronoteSessionManager(dummy_settings)
    mock_client = DummyStudentClient()
    mgr._client = mock_client
    return mgr

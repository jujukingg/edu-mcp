"""Unit tests for Pydantic models."""

from edu_mcp.models import (
    AbsenceDTO,
    CanteenMenuDTO,
    DelayDTO,
    GradeDTO,
    HomeworkDTO,
    LessonDTO,
    PeriodAveragesDTO,
    PunishmentDTO,
    SubjectAverageDTO,
    UserProfileDTO,
)


def test_user_profile_dto():
    dto = UserProfileDTO(name="Jean", student_class="Terminale")
    assert dto.name == "Jean"
    assert dto.student_class == "Terminale"
    assert dto.account_type == "student"


def test_lesson_dto():
    dto = LessonDTO(
        id="123",
        subject="Maths",
        start="2026-11-11T08:00:00",
        end="2026-11-11T09:00:00",
    )
    assert dto.subject == "Maths"
    assert dto.canceled is False


def test_grade_and_average_dto():
    grade = GradeDTO(
        id="g1",
        subject="Histoire",
        grade="16",
        out_of="20",
        coefficient="1",
        date="2026-11-11",
        period="Trimestre 1",
    )
    assert grade.grade == "16"

    avg = SubjectAverageDTO(subject="Histoire", student="15.0")
    period_avg = PeriodAveragesDTO(period="Trimestre 1", subjects=[avg])
    assert len(period_avg.subjects) == 1


def test_absence_delay_punishment_dto():
    abs_dto = AbsenceDTO(
        id="a1",
        from_date="2026-11-11T08:00:00",
        to_date="2026-11-11T10:00:00",
        justified=True,
        hours="2h00",
        reasons=["Médical"],
    )
    assert abs_dto.justified is True
    assert abs_dto.hours == "2h00"

    del_dto = DelayDTO(
        id="d1",
        date="2026-11-11T08:10:00",
        minutes="10",
        justified=False,
    )
    assert del_dto.minutes == "10"

    pun_dto = PunishmentDTO(
        id="p1",
        date="2026-11-11T16:00:00",
        nature="Retenue",
    )
    assert pun_dto.nature == "Retenue"


def test_canteen_menu_dto():
    menu = CanteenMenuDTO(
        date="2026-11-11",
        meal_name="Déjeuner",
        first_meal=["Salade"],
        main_meal=["Poulet rôti"],
        dessert=["Fruit"],
    )
    assert menu.meal_name == "Déjeuner"
    assert len(menu.main_meal) == 1

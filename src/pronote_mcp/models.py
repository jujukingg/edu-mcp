"""Pydantic data transfer models for Pronote objects."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ChildDTO(BaseModel):
    """Linked child in a parent account."""

    model_config = ConfigDict(frozen=True)

    name: str
    student_class: Optional[str] = None
    establishment: Optional[str] = None


class UserProfileDTO(BaseModel):
    """Student or parent account profile."""

    model_config = ConfigDict(frozen=True)

    name: str
    student_class: Optional[str] = None
    establishment: Optional[str] = None
    account_type: str = "student"
    active_child: Optional[str] = None
    children: List[ChildDTO] = Field(default_factory=list)


class LessonDTO(BaseModel):
    """Timetable lesson entry."""

    model_config = ConfigDict(frozen=True)

    id: str
    subject: str
    teacher: Optional[str] = None
    classroom: Optional[str] = None
    start: str
    end: str
    status: str = "normal"
    canceled: bool = False
    memo: Optional[str] = None


class HomeworkFileDTO(BaseModel):
    """Attachment file for homework."""

    model_config = ConfigDict(frozen=True)

    name: str
    url: str


class HomeworkDTO(BaseModel):
    """Homework assignment."""

    model_config = ConfigDict(frozen=True)

    id: str
    subject: str
    description: str
    due_date: str
    done: bool = False
    files: List[HomeworkFileDTO] = Field(default_factory=list)


class GradeDTO(BaseModel):
    """Individual grade entry."""

    model_config = ConfigDict(frozen=True)

    id: str
    subject: str
    grade: str
    out_of: str
    coefficient: str
    class_average: Optional[str] = None
    max: Optional[str] = None
    min: Optional[str] = None
    date: str
    period: str
    comment: Optional[str] = None


class SubjectAverageDTO(BaseModel):
    """Subject average statistics."""

    model_config = ConfigDict(frozen=True)

    subject: str
    student: Optional[str] = None
    class_average: Optional[str] = None
    max: Optional[str] = None
    min: Optional[str] = None


class PeriodAveragesDTO(BaseModel):
    """Averages for a school period (trimester/semester)."""

    model_config = ConfigDict(frozen=True)

    period: str
    overall_average: Optional[str] = None
    overall_class_average: Optional[str] = None
    subjects: List[SubjectAverageDTO] = Field(default_factory=list)


class AbsenceDTO(BaseModel):
    """Absence record."""

    model_config = ConfigDict(frozen=True)

    id: str
    from_date: str
    to_date: str
    justified: bool
    hours: Optional[str] = None
    reasons: Optional[List[str]] = Field(default_factory=list)


class DelayDTO(BaseModel):
    """Tardiness / delay record."""

    model_config = ConfigDict(frozen=True)

    id: str
    date: str
    minutes: Optional[str] = None
    justified: bool
    reasons: Optional[List[str]] = Field(default_factory=list)


class PunishmentDTO(BaseModel):
    """Disciplinary punishment / detention."""

    model_config = ConfigDict(frozen=True)

    id: str
    date: str
    given_by: Optional[str] = None
    reasons: Optional[List[str]] = Field(default_factory=list)
    circumstances: Optional[str] = None
    nature: Optional[str] = None
    duration: Optional[str] = None


class NewsItemDTO(BaseModel):
    """School news or notification."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    author: Optional[str] = None
    date: str
    content: str
    category: Optional[str] = None
    read: bool = True


class CanteenMenuDTO(BaseModel):
    """School canteen menu."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    date: str
    meal_name: str
    first_meal: List[str] = Field(default_factory=list)
    main_meal: List[str] = Field(default_factory=list)
    side_meal: List[str] = Field(default_factory=list)
    cheese: List[str] = Field(default_factory=list)
    dessert: List[str] = Field(default_factory=list)
    all_dishes: List[str] = Field(default_factory=list, alias="dishes")

    @property
    def dishes(self) -> List[str]:
        """Convenience property for accessing all dishes."""
        return self.all_dishes

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


class AttachmentDTO(BaseModel):
    """Generic attachment metadata for lessons, homework, and news."""

    model_config = ConfigDict(frozen=True)

    id: str = ""
    name: str
    url: str = ""
    type: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None


class LessonContentDTO(BaseModel):
    """Pedagogical content associated with a timetable lesson."""

    model_config = ConfigDict(frozen=True)

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    files: List[AttachmentDTO] = Field(default_factory=list)


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
    virtual_classrooms: List[str] = Field(default_factory=list)
    content: Optional[LessonContentDTO] = None


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
    files: List[AttachmentDTO] = Field(default_factory=list)


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


class DiscussionDTO(BaseModel):
    """Read-only summary of a Pronote discussion thread."""

    model_config = ConfigDict(frozen=True)

    id: str
    subject: str
    creator: Optional[str] = None
    date: str
    unread: bool = False
    closed: bool = False
    participants: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)


class MessageDTO(BaseModel):
    """Single message inside a Pronote discussion thread."""

    model_config = ConfigDict(frozen=True)

    id: str
    author: Optional[str] = None
    content: str
    date: str
    seen: bool = True


class AcquisitionDTO(BaseModel):
    """Competency acquisition level inside an evaluation."""

    model_config = ConfigDict(frozen=True)

    name: str
    domain: Optional[str] = None
    pillar: Optional[str] = None
    abbreviation: Optional[str] = None
    level: str
    coefficient: Optional[str] = None


class EvaluationDTO(BaseModel):
    """Competency-based evaluation entry."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    subject: str
    teacher: Optional[str] = None
    date: str
    domain: Optional[str] = None
    description: Optional[str] = None
    coefficient: Optional[str] = None
    acquisitions: List[AcquisitionDTO] = Field(default_factory=list)


class ReportSubjectDTO(BaseModel):
    """Subject appreciation inside a period report."""

    model_config = ConfigDict(frozen=True)

    subject: str
    comments: List[str] = Field(default_factory=list)


class ReportDTO(BaseModel):
    """School period report card appreciations."""

    model_config = ConfigDict(frozen=True)

    period: str
    overall_comments: List[str] = Field(default_factory=list)
    subjects: List[ReportSubjectDTO] = Field(default_factory=list)


class TeachingStaffDTO(BaseModel):
    """Teacher / staff member and associated subjects."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    type: Optional[str] = None
    subjects: List[str] = Field(default_factory=list)


class DownloadedFileDTO(BaseModel):
    """Metadata for a file downloaded or exported to local storage."""

    model_config = ConfigDict(frozen=True)

    filename: str
    saved_path: str
    size_bytes: int
    source_type: str


class GradeSimulationDTO(BaseModel):
    """Result of simulating a hypothetical grade."""

    model_config = ConfigDict(frozen=True)

    subject: str
    period: str
    current_subject_average: Optional[float] = None
    simulated_subject_average: float
    subject_delta: Optional[float] = None
    current_overall_average: Optional[float] = None
    simulated_overall_average: Optional[float] = None
    overall_delta: Optional[float] = None
    notes: str = ""


class SubjectProgressionDTO(BaseModel):
    """Comparison of a subject's average across two periods and vs class."""

    model_config = ConfigDict(frozen=True)

    subject: str
    previous_average: Optional[float] = None
    current_average: Optional[float] = None
    delta_period: Optional[float] = None
    class_average: Optional[float] = None
    gap_vs_class: Optional[float] = None


class ProgressionAnalysisDTO(BaseModel):
    """Overall academic progression between two school periods."""

    model_config = ConfigDict(frozen=True)

    previous_period: Optional[str] = None
    current_period: str
    current_overall: Optional[float] = None
    previous_overall: Optional[float] = None
    overall_delta: Optional[float] = None
    subjects: List[SubjectProgressionDTO] = Field(default_factory=list)


class WeeklyRadarDTO(BaseModel):
    """Weekly academic radar aggregating homework, schedule alerts, and unread messages."""

    model_config = ConfigDict(frozen=True)

    period_from: str
    period_to: str
    urgent_homework: List[HomeworkDTO] = Field(default_factory=list)
    canceled_or_modified_lessons: List[LessonDTO] = Field(default_factory=list)
    upcoming_tests: List[LessonDTO] = Field(default_factory=list)
    unread_discussions_count: int = 0

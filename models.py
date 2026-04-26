from pydantic import BaseModel
from typing import Optional


class EmailDTO(BaseModel):
    id: int
    uid: str
    sender: str
    subject: str
    body: str
    received_at: str
    category: str
    summary: str
    priority: str
    meeting_time: str = ""
    meeting_location: str = ""
    suggested_action: str = ""
    is_read: int
    is_deleted: int


class TemplateUpdateDTO(BaseModel):
    category: str
    content: str


class CategoriesUpdateDTO(BaseModel):
    categories: list[str]


class EmailStatusUpdateDTO(BaseModel):
    is_read: Optional[int] = None
    is_deleted: Optional[int] = None


class TemplateSuggestDTO(BaseModel):
    category: str
    current_template: str
    sample_summary: str = ""


class ReplySendDTO(BaseModel):
    body: str

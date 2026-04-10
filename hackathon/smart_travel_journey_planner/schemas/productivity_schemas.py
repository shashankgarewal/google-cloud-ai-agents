"""
schemas/productivity_schemas.py
Explicit, Vertex-safe Pydantic schemas for Google Workspace core tools.
Used to override problematic MCP schemas that lack explicit 'type' definitions.
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

class Attendee(BaseModel):
    email: str = Field(..., description="Email address of the attendee.")
    displayName: Optional[str] = Field(None, description="Name of the attendee.")
    responseStatus: Optional[str] = Field(None, description="Response status (needsAction, declined, tentative, accepted).")

class EventDateTime(BaseModel):
    dateTime: str = Field(..., description="The time, as a combined date-time value (ISO-8601).")
    timeZone: Optional[str] = Field(None, description="The time zone in which the time is specified.")

class ReminderOverride(BaseModel):
    method: str = Field("email", description="Method of reminder (e.g., email, popup).")
    minutes: int = Field(120, description="Number of minutes before the start of the event.")

class EventReminders(BaseModel):
    useDefault: bool = Field(False, description="Whether to use default reminders.")
    overrides: List[ReminderOverride] = Field(default_factory=list, description="Overrides for default reminders.")

class ManageEventParams(BaseModel):
    calendarId: str = Field("primary", description="Calendar identifier. To retrieve calendar IDs use the list_calendars tool.")
    eventId: Optional[str] = Field(None, description="The ID of the event to update. If omitted, a new event is created.")
    summary: str = Field(..., description="The title of the event.")
    location: Optional[str] = Field(None, description="The location of the event.")
    description: Optional[str] = Field(None, description="The description of the event.")
    start: EventDateTime = Field(..., description="The (inclusive) start time of the event.")
    end: EventDateTime = Field(..., description="The (exclusive) end time of the event.")
    # Removed Optional to avoid Vertex AI anyOf un-typable errors
    attendees: List[Attendee] = Field(default_factory=list, description="The list of attendees for the event.")
    # Swapped from Dict[str, Any] which breaks Vertex schema parsing
    reminders: EventReminders = Field(
        default_factory=lambda: EventReminders(useDefault=True), 
        description="Information about the event's reminders."
    )

class ManageTaskParams(BaseModel):
    tasklist: str = Field("@default", description="Task list identifier. To retrieve task list IDs use the list_tasklists tool.")
    task: Optional[str] = Field(None, description="The ID of the task to update. If omitted, a new task is created.")
    title: str = Field(..., description="The title of the task.")
    notes: Optional[str] = Field(None, description="Detailed notes about the task.")
    due: Optional[str] = Field(None, description="Due date of the task (ISO-8601).")
    status: Optional[str] = Field(None, description="Status of the task (needsAction, completed).")

class CreateDraftParams(BaseModel):
    to: List[str] = Field(..., description="List of recipient email addresses.")
    subject: str = Field(..., description="The subject of the email.")
    body: str = Field(..., description="The body of the email (plain text or HTML).")
    # Removed Optional from arrays
    cc: List[str] = Field(default_factory=list, description="List of CC recipient email addresses.")
    bcc: List[str] = Field(default_factory=list, description="List of BCC recipient email addresses.")

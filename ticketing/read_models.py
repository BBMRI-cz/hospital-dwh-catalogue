"""Typed read models for the ticketing presentation layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class TicketHistoryItem:
    item_name: str
    parent_dataset: str | None
    detail_url: str | None


@dataclass(slots=True)
class TicketHistoryEntry:
    subject: str
    description: str
    created_at: datetime
    items: list[TicketHistoryItem] = field(default_factory=list)

    @property
    def item_count(self) -> int:
        return len(self.items)

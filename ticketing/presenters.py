"""Presentation helpers for ticketing request and history views."""

from __future__ import annotations

from ticketing.models import TicketRequest
from ticketing.read_models import TicketHistoryEntry, TicketHistoryItem


def build_ticket_subject(cart: list[dict], default_subject: str) -> str:
    dataset_names = ', '.join(item['title'] for item in cart)
    return ((default_subject + f' \u2014 {dataset_names}') if dataset_names else default_subject)[
        :500
    ]


def build_ticket_description(description: str, cart: list[dict]) -> str:
    lines = [description]
    if cart:
        lines += ['', '--- Requested datasets ---']
        for item in cart:
            lines.append(f'  [{item["app"]}] {item["title"]} ({item["name"]})')
    return '\n'.join(lines)


def build_ticket_history_entries(tickets: list[TicketRequest]) -> list[TicketHistoryEntry]:
    entries: list[TicketHistoryEntry] = []
    for ticket in tickets:
        entries.append(
            TicketHistoryEntry(
                subject=ticket.subject,
                description=ticket.description,
                created_at=ticket.created_at,
                items=[
                    TicketHistoryItem(
                        item_name=item.item_name,
                        parent_dataset=item.parent_dataset,
                        detail_url=item.detail_url,
                    )
                    for item in ticket.items.all()
                ],
            )
        )
    return entries

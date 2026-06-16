"""Gmail tools — email_read (inbox) and email_send (outbound, with recipient fixups)."""

import base64
import json
import os
import re
from email.mime.text import MIMEText
from typing import Annotated

from googleapiclient.discovery import build
from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator

from auth.token_store import load_credentials_sync


def _get_gmail_service():
    creds = load_credentials_sync()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)

_PLACEHOLDER_RE = re.compile(
    r"example\.com|your[_-]?email|test@|placeholder@|@me\b",
    re.IGNORECASE,
)
_SELF_ALIASES = frozenset({"", "me", "myself", "user", "my email", "myself's email"})


class EmailReadInput(BaseModel):
    max_results: int = Field(5, ge=1, le=20, description="Number of emails to fetch")
    query: str = Field("", description="Gmail search query, e.g. 'is:unread' or 'from:alice@example.com'")


class EmailSendInput(BaseModel):
    to: str = Field(
        ...,
        description=(
            "Recipient email. Use the literal value 'me' when the user says 'mail me' "
            "or does not specify an address — never use example.com or made-up addresses."
        ),
    )
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Plain-text email body")

    @field_validator("to")
    @classmethod
    def normalize_to(cls, value: str) -> str:
        return value.strip()


def _user_email_from_env() -> str | None:
    email = os.getenv("USER_EMAIL", "").strip()
    return email or None


def _fetch_gmail_address(service) -> str:
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"]


def resolve_recipient(to: str, user_email: str) -> str:
    """Map 'mail me' / placeholders to the authenticated user's Gmail address."""
    cleaned = to.strip()
    if cleaned.lower() in _SELF_ALIASES or _PLACEHOLDER_RE.search(cleaned):
        return user_email
    if "@" not in cleaned:
        return user_email
    return cleaned


def _default_subject(subject: str) -> str:
    cleaned = subject.strip()
    return cleaned or "Message from your AI agent"


def _read_emails(max_results: int, query: str) -> str:
    service = _get_gmail_service()
    list_kwargs: dict = {"userId": "me", "maxResults": max_results}
    if query:
        list_kwargs["q"] = query
    listed = service.users().messages().list(**list_kwargs).execute()
    messages = listed.get("messages", [])
    results = []
    for item in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        snippet = msg.get("snippet", "")
        results.append(
            {
                "id": msg["id"],
                "from": headers.get("From"),
                "subject": headers.get("Subject"),
                "date": headers.get("Date"),
                "snippet": snippet,
            }
        )
    return json.dumps({"count": len(results), "emails": results}, indent=2)


def _send_email(to: str, subject: str, body: str) -> str:
    service = _get_gmail_service()
    user_email = _user_email_from_env() or _fetch_gmail_address(service)
    resolved_to = resolve_recipient(to, user_email)
    resolved_subject = _default_subject(subject)

    message = MIMEText(body)
    message["to"] = resolved_to
    message["subject"] = resolved_subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return json.dumps(
        {
            "status": "sent",
            "message_id": sent.get("id"),
            "to": resolved_to,
            "subject": resolved_subject,
            "requested_to": to if to.strip().lower() != resolved_to.lower() else None,
        }
    )


@tool(args_schema=EmailReadInput)
def email_read(
    max_results: Annotated[int, "Number of emails to fetch (1-20)"] = 5,
    query: Annotated[str, "Gmail search query"] = "",
) -> str:
    """Read recent emails from the user's Gmail inbox. Use Gmail query syntax for filters."""
    return _read_emails(max_results=max_results, query=query)


@tool(args_schema=EmailSendInput)
def email_send(
    to: Annotated[str, "Recipient — use 'me' when user says mail me; never example.com"],
    subject: Annotated[str, "Email subject line"],
    body: Annotated[str, "Plain-text email body"],
) -> str:
    """Send a plain-text email from the user's Gmail account."""
    return _send_email(to=to, subject=subject, body=body)

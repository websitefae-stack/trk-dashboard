"""
Google OAuth 2.0 helpers.

All token storage/retrieval goes through this module so the rest of the
app never touches raw credential fields directly.
"""

import datetime
import json

import frappe
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def _get_settings():
    settings = frappe.get_single("Calendar Sync Settings")
    if not settings.google_client_id or not settings.google_client_secret:
        frappe.throw("Google Client ID and Secret are not configured in Calendar Sync Settings.")
    return settings


def get_oauth_flow(redirect_uri: str = None) -> Flow:
    settings = _get_settings()
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.get_password("google_client_secret"),
            "redirect_uris": [redirect_uri or settings.redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri or settings.redirect_uri,
    )
    flow.oauth2session.params["access_type"] = "offline"
    flow.oauth2session.params["prompt"] = "consent"
    return flow


def get_credentials_for_person(doctype: str, name: str) -> Credentials | None:
    """
    Return a valid google.oauth2.credentials.Credentials object for the given
    Coach or Session Worker, refreshing the access token if necessary.
    """
    doc = frappe.get_doc(doctype, name)
    if not doc.google_sync_enabled or not doc.refresh_token:
        return None

    settings = _get_settings()
    creds = Credentials(
        token=doc.access_token or None,
        refresh_token=doc.get_password("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.get_password("google_client_secret"),
        scopes=SCOPES,
    )

    # Parse stored expiry
    if doc.token_expiry:
        if isinstance(doc.token_expiry, str):
            creds.expiry = datetime.datetime.fromisoformat(doc.token_expiry)
        else:
            creds.expiry = doc.token_expiry

    if creds.expired or not creds.valid:
        try:
            creds.refresh(Request())
            _save_tokens(doc, creds)
        except Exception as e:
            _mark_error(doc, str(e))
            return None

    return creds


def _save_tokens(doc, creds: Credentials):
    """Persist refreshed tokens back to the DocType."""
    doc.db_set("access_token", creds.token, update_modified=False)
    doc.db_set(
        "token_expiry",
        creds.expiry.isoformat() if creds.expiry else None,
        update_modified=False,
    )
    doc.db_set("connected", 1, update_modified=False)
    doc.db_set("last_error", None, update_modified=False)


def _mark_error(doc, error: str):
    doc.db_set("last_error", error[:500], update_modified=False)
    doc.db_set("connected", 0, update_modified=False)


def store_tokens_from_flow(doctype: str, name: str, flow: Flow, code: str):
    """Exchange auth code for tokens and store on the document."""
    flow.fetch_token(code=code)
    creds = flow.credentials

    doc = frappe.get_doc(doctype, name)
    doc.db_set("refresh_token", creds.refresh_token, update_modified=False)
    doc.db_set("access_token", creds.token, update_modified=False)
    doc.db_set(
        "token_expiry",
        creds.expiry.isoformat() if creds.expiry else None,
        update_modified=False,
    )
    doc.db_set("connected", 1, update_modified=False)
    doc.db_set("last_error", None, update_modified=False)

    # Discover the primary calendar ID automatically
    _discover_and_store_calendar_id(doctype, name, creds)


def _discover_and_store_calendar_id(doctype: str, name: str, creds: Credentials):
    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    calendar = service.calendars().get(calendarId="primary").execute()
    calendar_id = calendar.get("id", "primary")
    frappe.db.set_value(doctype, name, "google_calendar_id", calendar_id)

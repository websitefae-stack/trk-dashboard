"""
OAuth 2.0 endpoints for initiating and completing Google Calendar authorization.
"""

import urllib.parse

import frappe

from coach_calendar_sync.utils.google_auth import get_oauth_flow, store_tokens_from_flow


@frappe.whitelist()
def get_authorization_url(doctype: str, name: str):
    """
    Return the Google OAuth authorization URL for the given Coach or Session Worker.
    The state parameter encodes doctype:name so the callback can identify the record.
    """
    frappe.only_for("System Manager")
    redirect_uri = _redirect_uri()
    flow = get_oauth_flow(redirect_uri=redirect_uri)
    state = f"{doctype}:{name}"
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=urllib.parse.quote(state),
    )
    return auth_url


def callback():
    """
    Handle the OAuth redirect from Google.
    This is a web endpoint (not whitelisted) registered in hooks.py route rules.
    """
    args = frappe.local.request.args
    code = args.get("code")
    state = urllib.parse.unquote(args.get("state", ""))
    error = args.get("error")

    if error:
        frappe.respond_as_web_page(
            "Authorization Failed",
            f"Google returned an error: {error}",
            http_status_code=400,
        )
        return

    if not code or not state or ":" not in state:
        frappe.respond_as_web_page(
            "Invalid Request",
            "Missing authorization code or state.",
            http_status_code=400,
        )
        return

    doctype, name = state.split(":", 1)
    if doctype not in ("Coach", "Session Worker"):
        frappe.respond_as_web_page("Invalid DocType", "Unknown record type.", http_status_code=400)
        return

    redirect_uri = _redirect_uri()
    flow = get_oauth_flow(redirect_uri=redirect_uri)
    try:
        store_tokens_from_flow(doctype, name, flow, code)
    except Exception as e:
        frappe.respond_as_web_page(
            "Token Exchange Failed",
            f"Could not obtain tokens from Google: {e}",
            http_status_code=500,
        )
        return

    frappe.respond_as_web_page(
        "Connected",
        f"Google Calendar has been connected for {doctype} <strong>{name}</strong>. "
        "You can close this window.",
    )


@frappe.whitelist()
def disconnect(doctype: str, name: str):
    """Remove stored tokens and mark the record as disconnected."""
    frappe.only_for("System Manager")
    if doctype not in ("Coach", "Session Worker"):
        frappe.throw("Invalid DocType")

    frappe.db.set_value(
        doctype,
        name,
        {
            "refresh_token": None,
            "access_token": None,
            "token_expiry": None,
            "connected": 0,
            "google_calendar_id": None,
            "last_error": None,
        },
        update_modified=False,
    )
    return "Disconnected"


@frappe.whitelist()
def test_connection(doctype: str, name: str):
    """Verify credentials are valid by fetching the calendar list."""
    frappe.only_for("System Manager")
    from googleapiclient.discovery import build
    from coach_calendar_sync.utils.google_auth import get_credentials_for_person

    creds = get_credentials_for_person(doctype, name)
    if not creds:
        frappe.throw("No valid credentials found. Please reconnect.")

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    calendar = service.calendars().get(calendarId="primary").execute()

    doc = frappe.get_doc(doctype, name)
    frappe.db.set_value(doctype, name, "last_sync", frappe.utils.now(), update_modified=False)
    return {
        "status": "ok",
        "calendar_id": calendar.get("id"),
        "calendar_summary": calendar.get("summary"),
    }


def _redirect_uri() -> str:
    settings = frappe.get_single("Calendar Sync Settings")
    return settings.redirect_uri or (
        frappe.utils.get_url() + "/coach-calendar-sync/oauth/callback"
    )

"""
Client Report - a bespoke, one-off write-up about a specific client (a
progress report, session summary, etc), as opposed to:

- Notes (Client.session_notes) - quick per-session log entries, never
  client-facing.
- Client Document Share - sharing a reusable, franchise-wide Practice
  Document (a policy, form, ...) with a client, with its own signature/
  acknowledgement workflow. Reusing that for a bespoke report would mean
  creating a new "template" document per client per report, which
  defeats the whole point of that doctype being one template shared with
  many clients.

A report can be shown on the client's own Client Portal account
(show_on_portal, read by client_portal's own reports API), emailed to
them, both, or neither - independent toggles, since a coach might want
to draft one now and decide how (or whether) to share it later.
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime

from dashboard.api.shared.invoices import (
    _current_user_can_access_client,
    _get_current_coach_name,
    _client_display_name,
    get_client_email_options,
)
from dashboard.api.shared.email_templates import plain_text_to_email_html, parse_email_list

CLIENT_REPORT_DOCTYPE = "Client Report"


def _require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    return frappe.session.user


def _ensure_report_access(name):
    if not name or not frappe.db.exists(CLIENT_REPORT_DOCTYPE, name):
        frappe.throw(_("Report not found."))

    client_name = frappe.db.get_value(CLIENT_REPORT_DOCTYPE, name, "client")

    if not _current_user_can_access_client(client_name):
        frappe.throw(_("You do not have permission to access this report."), frappe.PermissionError)

    return frappe.get_doc(CLIENT_REPORT_DOCTYPE, name)


@frappe.whitelist()
def get_client_reports(client_name=None):
    _require_logged_in_user()

    client_name = (client_name or "").strip()

    if not client_name:
        frappe.throw(_("Client is required."))

    if not _current_user_can_access_client(client_name):
        frappe.throw(_("You do not have permission to access this client."), frappe.PermissionError)

    rows = frappe.get_all(
        CLIENT_REPORT_DOCTYPE,
        filters={"client": client_name},
        fields=[
            "name", "title", "report_date", "coach", "show_on_portal",
            "shared_on_portal_on", "last_emailed_on", "email_send_count", "modified",
        ],
        order_by="report_date desc, modified desc",
        limit_page_length=500,
        ignore_permissions=True,
    )

    for row in rows:
        row["coach_label"] = frappe.db.get_value("Coach", row.get("coach"), "coach_name") if row.get("coach") else ""

    return rows


@frappe.whitelist()
def get_client_report(name=None):
    _require_logged_in_user()

    doc = _ensure_report_access(name)

    return {
        "name": doc.name,
        "client": doc.client,
        "title": doc.title,
        "report_date": doc.report_date,
        "content": doc.content or "",
        "show_on_portal": int(doc.show_on_portal or 0),
        "shared_on_portal_on": doc.shared_on_portal_on,
        "last_emailed_on": doc.last_emailed_on,
        "email_send_count": int(doc.email_send_count or 0),
    }


@frappe.whitelist()
def save_client_report(name=None, client_name=None, title=None, report_date=None, content=None):
    _require_logged_in_user()

    name = (name or "").strip()
    title = (title or "").strip()

    if not title:
        frappe.throw(_("Title is required."))

    if name:
        doc = _ensure_report_access(name)
    else:
        client_name = (client_name or "").strip()

        if not client_name:
            frappe.throw(_("Client is required."))

        if not _current_user_can_access_client(client_name):
            frappe.throw(_("You do not have permission to access this client."), frappe.PermissionError)

        if not frappe.db.exists("Client", client_name):
            frappe.throw(_("Client not found."))

        doc = frappe.new_doc(CLIENT_REPORT_DOCTYPE)
        doc.client = client_name
        doc.coach = _get_current_coach_name()
        doc.created_by_user = frappe.session.user

    doc.title = title
    doc.report_date = report_date or doc.report_date or nowdate()
    doc.content = content or ""
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "name": doc.name}


@frappe.whitelist()
def delete_client_report(name=None):
    _require_logged_in_user()

    doc = _ensure_report_access(name)
    doc.delete(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def set_report_show_on_portal(name=None, show_on_portal=None):
    _require_logged_in_user()

    doc = _ensure_report_access(name)
    show_on_portal = str(show_on_portal).strip().lower() in ("1", "true", "yes", "on")

    doc.show_on_portal = 1 if show_on_portal else 0

    if show_on_portal and not doc.shared_on_portal_on:
        doc.shared_on_portal_on = now_datetime()

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def get_report_email_defaults(name=None):
    """
    Recipient options come straight from get_client_email_options() - the
    exact same client-email/contact list the generic "Send Email" and
    "Send Statement" buttons already offer, so there's only one place
    that logic lives.
    """
    _require_logged_in_user()

    doc = _ensure_report_access(name)
    client_label = _client_display_name(doc.client)

    email_options = get_client_email_options(client_name=doc.client)

    subject = f"Your report: {doc.title}"
    message = (
        f"Hi {client_label},\n"
        "\n"
        f"Please find your report \"{doc.title}\" below.\n"
        "\n"
        f"{doc.content or ''}"
    )

    return {"subject": subject, "message": message, "email_options": email_options}


@frappe.whitelist()
def send_client_report_email(name=None, recipient=None, subject=None, message=None, cc=None, sender=None, reply_to=None):
    _require_logged_in_user()

    doc = _ensure_report_access(name)
    recipient = (recipient or "").strip()

    if not recipient:
        frappe.throw(_("Recipient email is required."))

    subject = (subject or f"Your report: {doc.title}").strip()
    message = plain_text_to_email_html((message or "").strip())

    # Default to whoever's actually sending this, not the shared outgoing
    # account - matches send_client_email()'s own reasoning: otherwise
    # every client reply lands in office's inbox regardless of who
    # actually sent the report.
    reply_to = (reply_to or "").strip() or frappe.session.user

    kwargs = {
        "recipients": [recipient],
        "subject": subject,
        "message": message,
        "now": True,
        "reply_to": reply_to,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    sender = (sender or "").strip()
    if sender:
        kwargs["sender"] = sender

    frappe.sendmail(**kwargs)

    doc.last_emailed_on = now_datetime()
    doc.email_send_count = int(doc.email_send_count or 0) + 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}

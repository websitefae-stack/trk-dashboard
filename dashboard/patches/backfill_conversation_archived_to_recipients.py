"""
Archiving a Dashboard Conversation used to set its shared status field
to "Archived", moving the card to the Archived column for every
recipient at once the moment any one of them archived it - see
notifications.py's _set_my_archived_state() for the per-recipient fix.

Backfills every conversation already sitting at status="Archived" under
the old behaviour onto every one of its recipients' own "archived" row
instead (so nothing that currently looks archived to anyone suddenly
reappears on their board), then resets the conversation's own status
back to Open - left at "Archived" it would still leak through as
Archived to a recipient whose own row isn't (see _format_conversation()'s
fallback to doc.status when the current viewer's own row isn't archived).
"""

import frappe

CONVERSATION_DOCTYPE = "Dashboard Conversation"


def execute():
    if not frappe.db.exists("DocType", CONVERSATION_DOCTYPE):
        return

    try:
        _backfill()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "backfill_conversation_archived_to_recipients failed")


def _backfill():
    archived_conversations = frappe.get_all(
        CONVERSATION_DOCTYPE, filters={"status": "Archived"}, pluck="name"
    )

    for name in archived_conversations:
        doc = frappe.get_doc(CONVERSATION_DOCTYPE, name)

        for row in doc.get("recipients") or []:
            frappe.db.set_value(row.doctype, row.name, "archived", 1, update_modified=False)

        frappe.db.set_value(CONVERSATION_DOCTYPE, name, "status", "Open", update_modified=False)

    frappe.db.commit()

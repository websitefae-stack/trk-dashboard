"""
Corrects a bug in backfill_conversation_archived_to_recipients.py: it
reset a previously-archived conversation's shared status field back to
Open once its recipients' own archived rows were backfilled, on the
assumption nothing else still read that shared field. But
_format_conversation() only checks the CURRENT VIEWER's own recipient
row - a franchisor (or anyone else) who can see a conversation without
being a listed recipient on it (e.g. via the franchisor global-view
bypass in _current_user_can_see_conversation()) has no row of their own
to check, and fell back to the now-reset doc.status="Open" - so every
conversation that used to look Archived to a non-recipient viewer
suddenly looked active again the moment this deployed, exactly the
"hundreds of cards reopened" report this fixes.

Finds every conversation the previous patch touched and puts its status
back to Archived, without touching the recipient rows themselves (those
were backfilled correctly the first time). Deliberately narrower than
"any conversation with an archived recipient" - by now, some
conversations may have picked up one archived recipient for real,
through the new per-recipient Archive button working correctly, and
those must NOT have their status forced back (that would leak "Archived"
to their other, non-archived recipients too, reintroducing a milder
version of the original bug). The previous patch's own signature is
that it archived EVERY recipient of a conversation at once - nothing
else does that - so only conversations where every single recipient row
is archived are touched here.
"""

import frappe

CONVERSATION_DOCTYPE = "Dashboard Conversation"
RECIPIENT_DOCTYPE = "Dashboard Conversation Recipient"


def execute():
    if not frappe.db.exists("DocType", CONVERSATION_DOCTYPE):
        return

    try:
        _fix()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "fix_backfill_conversation_archived_regression failed")


def _fix():
    rows = frappe.db.sql(
        """
        select parent
        from `tabDashboard Conversation Recipient`
        group by parent
        having count(*) = sum(archived) and sum(archived) > 0
        """,
        as_dict=True,
    )

    for row in rows:
        frappe.db.set_value(CONVERSATION_DOCTYPE, row.parent, "status", "Archived", update_modified=False)

    frappe.db.commit()

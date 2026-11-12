"""
"also all the other documents are not showing like the form, the
practice manuals" - the real root cause, found this round:
SESSION_WORKER_LOGIN_FIELDS (practice_documents.py) never actually
included "sw_email", the real field this app uses everywhere else for
a session worker's login. _get_session_worker_login returned "" for
any session worker whose "user" field isn't linked to a real User
doctype record - which is most of them, since their logins are set up
via sw_email, not that link - and _ensure_brand_requirement silently
no-ops on an empty user with nothing logged. This was never limited to
the new Session Workers Can Access tick: Brand-Based Access document
assignment for session workers (sync_session_worker_brand_document_
requirements, already shipped before this session) has silently been
granting nothing to most session workers the whole time, for every
document type alike.

Re-runs the exact same resync activate_due_practice_documents (the
daily scheduled job) already does for every currently-Published
document, now that the login lookup is actually fixed - grants
whatever was silently withheld across every affected session worker,
not just the ones involved in today's testing.

Safe to re-run - _resync_practice_document_brand_access is already
written to be a no-op for anything already correctly synced.
"""

import frappe


def execute():
    from dashboard.api.shared.practice_documents import activate_due_practice_documents

    try:
        activate_due_practice_documents()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Resync All Session Worker Document Grants Failed")

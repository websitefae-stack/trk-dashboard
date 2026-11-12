"""
Re-runs the brand/session-worker access resync for every Published
Practice Document that already has Session Workers Can Access ticked
(SESSION WORKER HANDBOOK confirmed live) - that resync only ever fires
from Practice Document.on_update (an actual save) or the next day's
activate_due_practice_documents run, so a document ticked before this
deploy shipped the new sync logic (practice_documents.
_sync_session_worker_document_access) would otherwise sit unresolved
until someone happens to save it again or until tomorrow.

Safe to re-run - _resync_practice_document_brand_access is already
written to be a no-op for anything already correctly synced.
"""

import frappe


def execute():
    from dashboard.api.shared.practice_documents import (
        PRACTICE_DOCUMENT_DOCTYPE,
        _resync_practice_document_brand_access,
    )

    if not frappe.get_meta(PRACTICE_DOCUMENT_DOCTYPE).has_field("session_workers_can_access"):
        return

    names = frappe.get_all(
        PRACTICE_DOCUMENT_DOCTYPE,
        filters={"status": "Published", "session_workers_can_access": 1},
        pluck="name",
    )

    for name in names:
        try:
            _resync_practice_document_brand_access(name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Resync Session Worker Document Access Failed - {0}".format(name),
            )

    frappe.db.commit()

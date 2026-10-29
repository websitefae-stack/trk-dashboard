"""
Practice Document just gained published_date gating (access/requirements/
visibility withheld until that date, plus a "new document" notification
that previously didn't exist at all for Client Resource/Workshop Resource
documents) - see practice_documents.py's _publish_date_is_future(),
_notify_coaches_of_new_resource_document_if_due() and the new
coaches_notified field.

Without this, the very first daily run of activate_due_practice_documents()
(or the next unrelated save of any of these documents) would treat every
already-published document on the site as newly going live and notify
every entitled coach about all of them at once - a flood of "new
document" notifications for documents that have been live for months.

Marks every already-Published document whose published_date is blank or
already due (<= today) as already handled (coaches_notified=1) without
ever sending a notification for it - exactly what _should_notify_for_
publish_date()/_notify_coaches_of_new_resource_document_if_due() would
have done for a backfilled document anyway, just applied once up front
instead of per-document the next time each happens to be saved.

Deliberately leaves alone any Published document whose published_date is
still in the future (e.g. Ashley's own in-progress one that triggered
this feature) - that one hasn't gone live yet, and must still go through
the normal flow (grant access, notify) when its date actually arrives.
"""

import frappe
from frappe.utils import nowdate


def execute():
	if not frappe.db.exists("DocType", "Practice Document"):
		return

	if not frappe.get_meta("Practice Document").has_field("coaches_notified"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabPractice Document`
		SET coaches_notified = 1
		WHERE status = 'Published'
		  AND (published_date IS NULL OR published_date <= %s)
		  AND IFNULL(coaches_notified, 0) = 0
		""",
		(nowdate(),),
	)

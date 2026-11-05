"""
Practice Document just gained a franchisor-facing "new document"
notification (see practice_documents.py's _notify_franchisor_of_new_
practice_document_if_due and the new franchisor_notified field) -
Ashley asked for this after noticing 3 new Practice Manual documents
she'd added generated no notification to anyone, coach or franchisor.

Without this, the very next save of any already-published document (or
the next daily run of activate_due_practice_documents) would treat
every document already live on the site as newly published and notify
the franchisor about all of them at once. Marks every already-Published
document whose published_date is blank or already due (<= today) as
already handled, same backfill pattern as backfill_coaches_notified_
for_existing_practice_documents.py used for the equivalent coach flag.
"""

import frappe
from frappe.utils import nowdate


def execute():
	if not frappe.db.exists("DocType", "Practice Document"):
		return

	if not frappe.get_meta("Practice Document").has_field("franchisor_notified"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabPractice Document`
		SET franchisor_notified = 1
		WHERE status = 'Published'
		  AND (published_date IS NULL OR published_date <= %s)
		  AND IFNULL(franchisor_notified, 0) = 0
		""",
		(nowdate(),),
	)

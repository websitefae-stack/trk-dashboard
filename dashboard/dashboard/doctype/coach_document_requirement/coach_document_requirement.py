"""
The Before Submit compliance validation + completion audit script the
"My Documents" dashboard feature (dashboard.api.shared.compliance) relies
on and must never bypass or duplicate - it always drives completion
through requirement.submit(), never frappe.db.set_value(..., "docstatus", 1),
specifically so this runs every time.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class CoachDocumentRequirement(Document):
	def before_submit(self):
		if self.status == "Superseded":
			frappe.throw(_("This document has been superseded and can no longer be completed."))

		if self.status == "Completed":
			frappe.throw(_("This document has already been completed."))

		if self.required_action == "Read Only":
			if not self.read_confirmed:
				frappe.throw(_("Please confirm you have read this document before submitting."))
			self.read_confirmed_on = now_datetime()

		elif self.required_action == "Acknowledge":
			if not self.acknowledgement_confirmed:
				frappe.throw(_("Please confirm the acknowledgement before submitting."))
			self.acknowledged_on = now_datetime()

		elif self.required_action == "Sign":
			if not (self.typed_full_name or "").strip():
				frappe.throw(_("Please enter your full name before submitting."))
			if not self.signature:
				frappe.throw(_("Please sign the document before submitting."))
			if not self.signature_confirmed:
				frappe.throw(_("Please confirm the declaration before submitting."))
			self.signed_on = now_datetime()

		self.completed_on = now_datetime()
		self.completed_by = frappe.session.user
		self.status = "Completed"
		self.completion_reference = self.name

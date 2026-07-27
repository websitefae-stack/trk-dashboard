import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CoachDocumentRequirement(Document):
	def before_insert(self):
		if not self.assigned_on:
			self.assigned_on = now_datetime()

	def validate(self):
		if self.status == "Completed" and not self.completed_on:
			self.completed_on = now_datetime()

		if self.status != "Completed":
			self.completed_on = None

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CoachOnboardingStep(Document):
	def validate(self):
		if self.has_value_changed("status"):
			if self.status == "Done" and not self.completed_on:
				self.completed_on = now_datetime()
				self.completed_by = frappe.session.user
			elif self.status != "Done":
				self.completed_on = None
				self.completed_by = None

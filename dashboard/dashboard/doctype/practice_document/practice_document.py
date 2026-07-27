import frappe
from frappe import _
from frappe.model.document import Document


class PracticeDocument(Document):
	def validate(self):
		self.validate_audience()

	def validate_audience(self):
		"""
		Internal Compliance and Both need an assignment audience - that's who
		the Coach Document Requirement gets created for. A pure Client
		Resource never creates a Coach Document Requirement at all, so it
		doesn't need one; All Coaches/Selected People or Roles are optional
		there and only narrow who can see it in their Client Resources
		library if set.
		"""
		if self.document_purpose not in ("Internal Compliance", "Both"):
			return

		if not self.all_coaches and not self.get("selected_people_or_roles"):
			frappe.throw(
				_(
					"Choose All Coaches, or add at least one coach under Selected "
					"People or Roles - a {0} document needs an assignment audience."
				).format(self.document_purpose)
			)

	def on_update(self):
		from dashboard.api.shared.practice_documents import sync_coach_document_requirements

		sync_coach_document_requirements(self)

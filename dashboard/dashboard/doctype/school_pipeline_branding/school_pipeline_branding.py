import frappe
from frappe.model.document import Document


class SchoolPipelineBranding(Document):
	pass


def get_settings():
	return frappe.get_single("School Pipeline Branding")

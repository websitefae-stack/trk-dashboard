import frappe
from frappe.model.document import Document


class FormVisibilityRule(Document):
    def validate(self):
        row = frappe.db.get_value(
            "DocType", self.form_doctype, ["module", "istable", "issingle"], as_dict=True
        )

        if not row or row.module != "Forms" or row.istable or row.issingle:
            frappe.throw("Form must be a DocType in the site's \"Forms\" module.")

"""
Retrofits two School Pipeline changes onto sites where
create_school_pipeline_doctypes.py already ran (so its own, now-updated
field definitions won't apply on their own - that patch only creates
the doctypes if they don't already exist):

- School gets a new "area" field (e.g. "Cheshire", "Hartford") - needed
  for the bulk import Ashley's running, which groups/filters schools by
  area.
- School Contact's "role" options gains "Deputy Head", alongside the
  existing SENCO/Head/Reception/Other.
"""

import frappe


def execute():
    if frappe.db.exists("DocType", "School"):
        doc = frappe.get_doc("DocType", "School")
        has_area_field = any(field.fieldname == "area" for field in doc.fields)
        if not has_area_field:
            doc.append("fields", {
                "fieldname": "area",
                "fieldtype": "Data",
                "label": "Area",
                "in_list_view": 1,
                "in_standard_filter": 1,
            })
            doc.save(ignore_permissions=True)

    if frappe.db.exists("DocType", "School Contact"):
        doc = frappe.get_doc("DocType", "School Contact")
        for field in doc.fields:
            if field.fieldname == "role" and "Deputy Head" not in (field.options or ""):
                field.options = "\nSENCO\nHead\nDeputy Head\nReception\nOther"
                doc.save(ignore_permissions=True)
                break

    frappe.db.commit()

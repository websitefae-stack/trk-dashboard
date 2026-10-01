"""
Retrofits a "token" field onto Franchise Brochure Request (on sites
where create_franchise_brochure_request_form.py already ran) - a
random, unguessable string generated once per request (see
franchise_brochure.send_brochure_link) that gates /franchise-brochure
on resilient_domains: the brochure page is only ever reachable via
?token=<this value>, not just "unlisted" the way the original design
left it, so it actually requires having requested it rather than
merely not being linked from anywhere.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Franchise Brochure Request"):
        return

    doc = frappe.get_doc("DocType", "Franchise Brochure Request")
    has_field = any(field.fieldname == "token" for field in doc.fields)

    if not has_field:
        doc.append("fields", {
            "fieldname": "token",
            "fieldtype": "Data",
            "label": "Access Token",
            "unique": 1,
            "read_only": 1,
            "no_copy": 1,
            "description": "Generated automatically - gates the brochure page, never shown/editable in the form itself.",
        })
        doc.save(ignore_permissions=True)

    frappe.db.commit()

"""
One-off, read-only diagnostic - Ashley merged several duplicate "Sam/
Samantha Male" Contact records via Desk's native "Merge With" feature,
and the franchisor Contacts list page is now linking to a Contact
literally named "Samantha Male-Samantha Male", which doesn't exist
("Contact not found: Samantha Male-Samantha Male"). The link-building
code itself (franchisor_db/contacts/index.html) just uses the Contact's
own name/ID directly - so this means either that exact record exists
with a broken name, or something else (a Client/Lead's stored contact
reference) still points at a name that no longer resolves.

Logs:
1. Whether a Contact named exactly "Samantha Male-Samantha Male" exists.
2. Every current Contact whose name/first_name/last_name contains "sam"
   (case-insensitive), to see the real post-merge state.
3. Any Client or Client Lead record whose contact-reference field still
   points at the broken name, so the dangling reference (if that's what
   this is) is visible instead of guessed at.

Safe to delete once the cause is found and the actual record fixed by
hand in Desk.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Contact"):
        frappe.log_error("Contact doctype does not exist", "Diag: Samantha Male contact merge")
        return

    broken_name_exists = frappe.db.exists("Contact", "Samantha Male-Samantha Male")
    broken_name_doc = None
    if broken_name_exists:
        broken_name_doc = frappe.db.get_value(
            "Contact", "Samantha Male-Samantha Male",
            ["name", "first_name", "last_name", "creation", "modified"],
            as_dict=True,
        )

    sam_contacts = []
    for fieldname in ("first_name", "last_name"):
        if frappe.get_meta("Contact").has_field(fieldname):
            sam_contacts += frappe.get_all(
                "Contact",
                filters={fieldname: ["like", "%sam%"]},
                fields=["name", "first_name", "last_name", "creation", "modified"],
            )
    seen = {row["name"]: row for row in sam_contacts}

    dangling_refs = []
    for doctype, fieldname in [("Client", "contact"), ("Client", "billing_contact"), ("Client Lead", "contact")]:
        meta = frappe.get_meta(doctype) if frappe.db.exists("DocType", doctype) else None
        if not meta or not meta.has_field(fieldname):
            continue
        rows = frappe.get_all(
            doctype,
            filters={fieldname: "Samantha Male-Samantha Male"},
            fields=["name", fieldname],
        )
        for row in rows:
            dangling_refs.append({"doctype": doctype, "field": fieldname, **row})

    message = (
        f"Broken-name Contact exists: {bool(broken_name_exists)}\n"
        f"Its row: {broken_name_doc}\n\n"
        f"Current Contacts matching 'sam' in first/last name:\n"
        + "\n".join(str(row) for row in seen.values())
        + "\n\n"
        f"Records still referencing 'Samantha Male-Samantha Male' directly:\n"
        + "\n".join(str(row) for row in dangling_refs)
    )

    frappe.log_error(message, "Diag: Samantha Male contact merge")

import json
import frappe
from frappe import _


TEXTAREA_TYPES = {"Text", "Small Text", "Long Text", "Code", "Text Editor"}

SKIP_FIELDTYPES = {
    "Section Break",
    "Column Break",
    "Tab Break",
    "HTML",
    "Button",
    "Fold",
    "Heading",
    "Image",
    "Table",
    "Table MultiSelect",
}


def require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def get_or_create_contact_for_customer(customer_name):
    if not customer_name:
        return None

    existing = frappe.db.get_value(
        "Contact",
        {"custom_customer": customer_name},
        ["name", "full_name", "email_id", "mobile_no"],
        as_dict=True,
    )

    if existing:
        return existing

    customer = frappe.db.get_value(
        "Customer",
        customer_name,
        ["name", "customer_name", "email_id", "mobile_no", "phone"],
        as_dict=True,
    )

    if not customer:
        return None

    contact = frappe.new_doc("Contact")
    contact.first_name = customer.get("customer_name") or customer.get("name")

    if contact.meta.has_field("email_id"):
        contact.email_id = customer.get("email_id") or ""

    if contact.meta.has_field("mobile_no"):
        contact.mobile_no = customer.get("mobile_no") or customer.get("phone") or ""

    if contact.meta.has_field("custom_customer"):
        contact.custom_customer = customer_name

    contact.append("links", {
        "link_doctype": "Customer",
        "link_name": customer_name,
    })

    contact.insert(ignore_permissions=True)

    return frappe.db.get_value(
        "Contact",
        contact.name,
        ["name", "full_name", "email_id", "mobile_no"],
        as_dict=True,
    )


def sync_billing_contact(doc):
    customer_name = doc.get("billing_contact")
    if not customer_name:
        return

    contact = get_or_create_contact_for_customer(customer_name)
    if not contact:
        return

    for row in doc.get("client_contacts") or []:
        if row.get("contact") == contact.get("name"):
            return

    child = doc.append("client_contacts", {})

    if child.meta.has_field("contact"):
        child.contact = contact.get("name")

    if child.meta.has_field("contact_name"):
        child.contact_name = contact.get("full_name") or contact.get("name")

    if child.meta.has_field("phone"):
        child.phone = contact.get("mobile_no") or ""

    if child.meta.has_field("email_id"):
        child.email_id = contact.get("email_id") or ""


@frappe.whitelist()
def get_link_options(doctype, txt=None, limit_page_length=200):
    require_logged_in_user()

    return frappe.get_list(
        doctype,
        fields=["name"],
        order_by="name asc",
        limit_page_length=int(limit_page_length or 200),
    )


@frappe.whitelist()
def save_client(docname=None, data=None):
    require_logged_in_user()

    payload = json.loads(data) if isinstance(data, str) else (data or {})

    if docname:
        doc = frappe.get_doc("Client", docname)
    else:
        doc = frappe.new_doc("Client")

    meta = frappe.get_meta("Client")

    always_editable_fields = {
        "full_name",
        "gender_identity",
        "company",
        "primary_coach",
        "attending_coach",
        "session_worker",
        "pricelist",
        "billing_contact",
    }

    editable_fields = {
        df.fieldname: df
        for df in meta.fields
        if df.fieldname
        and not df.hidden
        and (not df.read_only or df.fieldname in always_editable_fields)
        and df.fieldtype not in SKIP_FIELDTYPES
    }

    for fieldname, df in editable_fields.items():
        if fieldname not in payload:
            continue

        value = payload.get(fieldname)

        if df.fieldtype == "Check":
            value = 1 if str(value).lower() in ("1", "true", "yes", "on") else 0

        if df.fieldtype in ("Float", "Currency", "Percent"):
            value = float(value or 0)

        if df.fieldtype == "Int":
            value = int(float(value or 0))

        doc.set(fieldname, value)

    sync_billing_contact(doc)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"name": doc.name}

import json
import frappe
from frappe import _
from dashboard.api.coach.clients import (
    ensure_coach_client_access,
    get_coach_display_name,
)
from dashboard.api.shared.client_details import add_client_note as shared_add_client_note


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


LAYOUT = [
    {
        "tab": "Details",
        "sections": [
            {
                "title": "Profile",
                "columns": 2,
                "fields": [
                    {"label": "Full Name"},
                    {"label": "Preferred Name"},
                    {"label": "Mobile"},
                    {"label": "Email"},
                    {"label": "Date Of Birth"},
                    {"label": "Age"},
                    {"label": "Address"},
                    {"label": "City"},
                    {"label": "Zip Code"},
                    
                ],
            },
            {
                "title": "Identity",
                "columns": 3,
                "fields": [
                    {"label": "Sex"},
                    {"label": "Gender"},
                    {"label": "Pronouns"},
                ],
            },
            {
                "title": "Medical",
                "columns": 2,
                "fields": [
                    {"label": "Neurodiverse Status"},
                    {"label": "Neurodiverse Information", "full_width": True},
                    {"label": "Allergies", "full_width": True},
                ],
            },
        ],
    },
    {
        "tab": "Administration",
        "sections": [
            {
                "title": "Admin",
                "columns": 2,
                "fields": [
                    {"label": "Status"},
                    {"label": "Client Type"},
                    {"label": "Primary Coach"},
                    {"label": "Attending Coach"},
                    {"label": "Session Worker"},
                    {"label": "Coach Banking Details"},
                    {"label": "Pricelist"},
                    {"label": "Company"},
                ],
            },
        ],
    },
    {"tab": "Contacts", "custom": "contacts"},
    {"tab": "Notes", "custom": "notes"},
    {"tab": "Appointments", "custom": "appointments"},
    {"tab": "Billing", "custom": "billing"},
]


def require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def normalize(text):
    return (text or "").strip().lower()


def field_meta_lookup(meta):
    by_label = {}
    by_fieldname = {}

    for df in meta.fields:
        if not df.fieldname:
            continue

        by_fieldname[df.fieldname] = df

        if df.label:
            by_label[normalize(df.label)] = df

    return by_label, by_fieldname


def build_field(df, doc, config):
    value = doc.get(df.fieldname)

    return {
        "fieldname": df.fieldname,
        "label": df.label or df.fieldname.replace("_", " ").title(),
        "fieldtype": df.fieldtype,
        "options": df.options or "",
        "reqd": int(df.reqd or 0),
        "read_only": int(df.read_only or 0),
        "description": df.description or "",
        "value": value if value is not None else "",
        "is_textarea": df.fieldtype in TEXTAREA_TYPES,
        "is_check": df.fieldtype == "Check",
        "is_select": df.fieldtype == "Select",
        "is_link": df.fieldtype == "Link",
        "is_full_width": bool(config.get("full_width")) or df.fieldtype in TEXTAREA_TYPES,
    }


def build_tabs(doc):
    meta = frappe.get_meta("Client")
    by_label, by_fieldname = field_meta_lookup(meta)

    tabs = []

    for tab_cfg in LAYOUT:
        tab = {
            "label": tab_cfg["tab"],
            "custom": tab_cfg.get("custom", ""),
            "sections": [],
        }

        if tab_cfg.get("custom"):
            tabs.append(tab)
            continue

        for sec_cfg in tab_cfg["sections"]:
            section = {
                "title": sec_cfg.get("title", ""),
                "columns": sec_cfg.get("columns", 2),
                "fields": [],
            }

            used_fieldnames = set()

            for field_cfg in sec_cfg.get("fields", []):
                df = None

                if field_cfg.get("fieldname"):
                    df = by_fieldname.get(field_cfg["fieldname"])
                elif field_cfg.get("label"):
                    df = by_label.get(normalize(field_cfg["label"]))

                if not df or df.hidden or df.fieldname in used_fieldnames:
                    continue

                used_fieldnames.add(df.fieldname)
                section["fields"].append(build_field(df, doc, field_cfg))

            tab["sections"].append(section)

        tabs.append(tab)

    return tabs


def get_contact_data(contact_name):
    if not contact_name or not frappe.db.exists("Contact", contact_name):
        return {
            "display_name": contact_name or "",
            "phone": "",
            "email": "",
            "company": "",
        }

    contact = frappe.db.get_value(
        "Contact",
        contact_name,
        [
            "name",
            "full_name",
            "first_name",
            "last_name",
            "email_id",
            "mobile_no",
            "phone",
            "company_name",
        ],
        as_dict=True,
    ) or {}

    display_name = (
        contact.get("full_name")
        or " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")])).strip()
        or contact_name
    )

    return {
        "display_name": display_name,
        "phone": contact.get("mobile_no") or contact.get("phone") or "",
        "email": contact.get("email_id") or "",
        "company": contact.get("company_name") or "",
    }


def find_contact_for_customer(customer_name):
    if not customer_name:
        return None

    contact = frappe.db.get_value(
        "Contact",
        {"custom_customer": customer_name},
        ["name", "full_name", "first_name", "last_name", "email_id", "mobile_no", "phone"],
        as_dict=True,
    )

    if contact:
        return contact

    return None


def get_billing_contact(doc, contact_detail_base_url="/coach_db/contact_details"):
    customer_name = doc.get("billing_contact")

    if not customer_name:
        return None

    contact = find_contact_for_customer(customer_name)

    if contact:
        display_name = (
            contact.get("full_name")
            or " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")])).strip()
            or contact.get("name")
        )

        return {
            "name": contact.get("name"),
            "display_name": display_name,
            "phone": contact.get("mobile_no") or contact.get("phone") or "",
            "email": contact.get("email_id") or "",
            "relationship": "",
            "link": f"{contact_detail_base_url}?name={contact.get('name')}",
        }

    return {
        "name": customer_name,
        "display_name": customer_name,
        "phone": "",
        "email": "",
        "relationship": "",
        "link": "",
    }


def get_client_contacts(doc, contact_detail_base_url="/coach_db/contact_details"):
    contacts = []

    for row in doc.get("client_contacts") or []:
        contact_name = row.get("contact")
        contact_data = get_contact_data(contact_name)

        contacts.append(
            {
                "contact": contact_name,
                "contact_name": row.get("contact_name") or contact_data.get("display_name") or contact_name or "Contact",
                "phone": row.get("phone") or contact_data.get("phone") or "",
                "email": row.get("email_id") or contact_data.get("email") or "",
                "company": contact_data.get("company") or "",
                "relationship": row.get("relationship") or row.get("relation") or "",
                "link": f"{contact_detail_base_url}?name={contact_name}" if contact_name else "",
            }
        )

    return contacts


def get_session_notes(doc):
    notes = []

    for row in doc.get("session_notes") or []:
        user = row.get("user") or row.get("owner") or row.get("created_by") or ""

        notes.append(
            {
                "session_date": row.get("session_date"),
                "session_type": row.get("session_type"),
                "notes": row.get("notes") or row.get("note") or row.get("note_text") or "",
                "user": user,
                "user_full_name": frappe.get_cached_value("User", user, "full_name") or user,
                "idx": row.get("idx") or 0,
                "creation": row.get("creation"),
            }
        )

    notes.sort(
        key=lambda note: (
            note.get("session_date") or "",
            note.get("creation") or "",
            note.get("idx") or 0,
        ),
        reverse=True,
    )

    return notes


def status_is_cancelled(status):
    return normalize(status) in {
        "cancelled",
        "canceled",
        "cancelled by client",
        "cancelled by coach",
        "cancelled by session worker",
    }


def get_item_display_name(item_code):
    if not item_code:
        return ""

    if frappe.db.exists("Item", item_code):
        item_name = frappe.db.get_value("Item", item_code, "item_name")
        return item_name or item_code

    return item_code


def get_client_appointments(client_name, calendar_detail_base_url="/coach_db/calendar_details"):
    if not client_name or not frappe.db.exists("DocType", "Client Appointment"):
        return []

    fields = [
        "name",
        "appointment_start",
        "appointment_end",
        "item",
        "status",
        "client_package",
        "client_package_balance",
        "session_number",
        "total_sessions",
        "progress_text",
        "booking_warning",
        "linked_event",
    ]

    rows = frappe.get_all(
        "Client Appointment",
        filters={"client": client_name},
        fields=fields,
        order_by="appointment_start desc, creation desc",
        limit_page_length=200,
    )

    result = []

    for row in rows:
        status = row.get("status") or ""

        if status_is_cancelled(status):
            continue

        row["display_status"] = status
        row["display_progress"] = row.get("progress_text") or "—"
        row["item_display_name"] = get_item_display_name(row.get("item"))
        row["view_link"] = (
            f"{calendar_detail_base_url}?event={row.get('linked_event')}"
            if row.get("linked_event")
            else ""
        )

        result.append(row)

    return result


def whole_number(value):
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def get_package_balance_date(row):
    for fieldname in ["posting_date", "date", "transaction_date", "creation"]:
        if row.get(fieldname):
            return row.get(fieldname)

    return None


def get_package_balances(client_name):
    if not client_name or not frappe.db.exists("DocType", "Client Package Balance"):
        return []

    fields = [
        "name",
        "client_package",
        "service_item",
        "qty_purchased",
        "qty_booked",
        "qty_used",
        "qty_available",
        "status",
        "sales_invoice",
        "invoice_status",
        "outstanding_amount",
        "parent_checkins_due",
        "creation",
    ]

    optional_fields = ["posting_date", "date", "transaction_date"]

    for fieldname in optional_fields:
        if frappe.db.has_column("Client Package Balance", fieldname):
            fields.append(fieldname)

    rows = frappe.get_all(
        "Client Package Balance",
        filters={"client": client_name},
        fields=fields,
        order_by="creation desc",
        limit_page_length=200,
    )

    for row in rows:
        purchased = whole_number(row.get("qty_purchased"))
        booked = whole_number(row.get("qty_booked"))
        used = whole_number(row.get("qty_used"))
        available = whole_number(row.get("qty_available"))

        row["qty_purchased"] = purchased
        row["qty_booked"] = booked
        row["qty_used"] = used
        row["qty_available"] = available
        row["appointments_to_add"] = max(purchased - booked, 0)
        row["display_date"] = get_package_balance_date(row)

    return rows


def get_client_invoices(client_name):
    if not client_name or not frappe.db.exists("DocType", "Sales Invoice"):
        return []

    return frappe.get_all(
        "Sales Invoice",
        filters={"custom_client": client_name},
        fields=[
            "name",
            "posting_date",
            "due_date",
            "customer",
            "grand_total",
            "outstanding_amount",
            "status",
            "docstatus",
        ],
        order_by="posting_date desc, creation desc",
        limit_page_length=200,
    )


@frappe.whitelist()
def get_link_options(doctype, txt=None, limit_page_length=200):
    require_logged_in_user()

    if not doctype:
        return []

    return frappe.get_list(
        doctype,
        fields=["name"],
        order_by="name asc",
        limit_page_length=int(limit_page_length or 200),
    )


@frappe.whitelist()
def save_client(docname=None, data=None):
    require_logged_in_user()

    if docname:
        ensure_coach_client_access(docname)

    payload = json.loads(data) if isinstance(data, str) else (data or {})

    if docname:
        doc = frappe.get_doc("Client", docname)
    else:
        doc = frappe.new_doc("Client")

    meta = frappe.get_meta("Client")

    editable_fields = {
        df.fieldname: df
        for df in meta.fields
        if df.fieldname
        and not df.hidden
        and not df.read_only
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

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"name": doc.name}


@frappe.whitelist()
def add_client_note(client_name, note_text):
    ensure_coach_client_access(client_name)
    return shared_add_client_note(client_name=client_name, note_text=note_text)


def get_client_context_data(client_name=None, is_new=False, base_url="/coach_db", enforce_access=True):
    require_logged_in_user()

    if client_name and not is_new and enforce_access:
        ensure_coach_client_access(client_name)

    if client_name and not is_new:
        doc = frappe.get_doc("Client", client_name)
        title = doc.get("full_name") or doc.name
    else:
        doc = frappe.new_doc("Client")
        title = "New Client"

    is_existing_client = bool(doc.name and not is_new)

    return {
        "client_docname": doc.name if is_existing_client else "",
        "client_title": title,
        "tabs": build_tabs(doc),
        "billing_contact": get_billing_contact(doc, f"{base_url}/contact_details"),
        "client_contacts": get_client_contacts(doc, f"{base_url}/contact_details"),
        "session_notes": get_session_notes(doc),
        "client_appointments": get_client_appointments(
            doc.name if is_existing_client else "",
            f"{base_url}/calendar_details",
        ),
        "package_balances": get_package_balances(doc.name if is_existing_client else ""),
        "client_invoices": get_client_invoices(doc.name if is_existing_client else ""),
        "travel_charged": int(doc.get("travel_charged") or 0),
        "travel_miles_one_way": doc.get("travel_miles_one_way") or 0,
    }


def get_coach_name():
    return get_coach_display_name()

import json
import frappe
from frappe import _

from dashboard.api.shared.permissions import (
    ensure_client_access,
    ensure_logged_in,
)

from dashboard.api.shared.directory import (
    get_coach_display_name,
    get_franchisor_display_name,
    get_user_display_name,
)


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
    "Table MultiSelect",
}

FORCE_EDITABLE_FIELDS = {
    "name1",
    "first_name",
    "middle_name",
    "last_name",
    "preferred_name",
    "therapy_location",
    "gender",
    "gender_identity",
    "sex",
    "company",
    "primary_coach",
    "attending_coach",
    "session_worker",
    "pricelist",
    "price_list",
    "billing_contact",
    "travel_charged",
    "travel_miles_one_way",
}


LAYOUT = [
    {
        "tab": "Details",
        "sections": [
            {
                "title": "Profile",
                "columns": 2,
                "fields": [
                    {"label": "Full Name", "candidates": ["full_name"]},
                    {"label": "First Name", "candidates": ["name1", "first_name"]},
                    {"label": "Middle Name", "candidates": ["middle_name"]},
                    {"label": "Last Name", "candidates": ["last_name"]},
                    {"label": "Preferred Name", "candidates": ["preferred_name"]},
                    {"label": "Mobile", "candidates": ["mobile", "phone"]},
                    {"label": "Email", "candidates": ["email", "email_id"]},
                    {"label": "Date Of Birth", "candidates": ["date_of_birth", "birth_date", "dob"]},
                    {"label": "Age", "candidates": ["age"]},
                    {"label": "Address", "candidates": ["address"]},
                    {"label": "City", "candidates": ["city"]},
                    {"label": "Zip Code", "candidates": ["zip_code", "postcode", "postal_code"]},
                ],
            },
            {
                "title": "Identity",
                "columns": 3,
                "fields": [
                    {"label": "Sex", "candidates": ["sex"]},
                    {"label": "Gender Identity", "display_label": "Gender", "candidates": ["gender_identity", "gender"]},
                    {"label": "Pronouns", "candidates": ["pronouns"]},
                ],
            },
            {
                "title": "Medical",
                "columns": 2,
                "fields": [
                    {"label": "Neurodiverse Status", "candidates": ["neurodiverse_status"]},
                    {"label": "Allergies", "candidates": ["allergies"]},
            
                    {"label": "Neurodiverse Information", "candidates": ["neurodiverse_information"]},
                    {"label": "Diagnosis", "candidates": ["diagnosis"]},
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
                    {"label": "Status", "candidates": ["status"]},
                    {"label": "Client Type", "candidates": ["client_type"]},
                    {"label": "Primary Coach", "candidates": ["primary_coach"]},
                    {"label": "Attending Coach", "candidates": ["attending_coach"]},
                    {"label": "Session Worker", "candidates": ["session_worker"]},
                    {"label": "Billing Contact", "candidates": ["billing_contact"]},
                    {"label": "Coach Banking Details", "candidates": ["coach_banking_details"]},
                    {"label": "Pricelist", "candidates": ["pricelist", "price_list"]},
                    {"label": "Company", "candidates": ["company"]},
                    {"label": "Main Therapy Location", "candidates": ["therapy_location"]},
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
    ensure_logged_in()


def get_coach_name():
    return get_coach_display_name()


def get_franchisor_name():
    return get_franchisor_display_name()


def get_session_worker_name():
    return get_user_display_name()


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


def find_field(field_cfg, by_label, by_fieldname):
    for fieldname in field_cfg.get("candidates") or []:
        if fieldname in by_fieldname:
            return by_fieldname[fieldname]

    if field_cfg.get("fieldname"):
        return by_fieldname.get(field_cfg["fieldname"])

    if field_cfg.get("label"):
        return by_label.get(normalize(field_cfg["label"]))

    return None


def build_field(df, doc, config, is_new=False):
    value = doc.get(df.fieldname)

    force_editable = df.fieldname in FORCE_EDITABLE_FIELDS

    if df.fieldname == "full_name":
        read_only = 0 if is_new else 1
    else:
        read_only = 0 if force_editable else int(df.read_only or 0)

    return {
        "fieldname": df.fieldname,
        "label": config.get("display_label") or df.label or df.fieldname.replace("_", " ").title(),
        "fieldtype": df.fieldtype,
        "options": df.options or "",
        "reqd": int(df.reqd or 0),
        "read_only": read_only,
        "description": df.description or "",
        "value": value if value is not None else "",
        "is_textarea": df.fieldtype in TEXTAREA_TYPES,
        "is_check": df.fieldtype == "Check",
        "is_select": df.fieldtype == "Select",
        "is_link": df.fieldtype == "Link",
        "is_full_width": bool(config.get("full_width")) or df.fieldtype in TEXTAREA_TYPES,
        "is_table": df.fieldtype == "Table",
        "table_rows": [row.as_dict() for row in doc.get(df.fieldname)] if df.fieldtype == "Table" else [],
    }


def build_tabs(doc, is_new=False):
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

            for field_cfg in sec_cfg.get("fields") or []:
                df = find_field(field_cfg, by_label, by_fieldname)

                if not df or df.hidden or df.fieldname in used_fieldnames:
                    continue

                used_fieldnames.add(df.fieldname)
                section["fields"].append(build_field(df, doc, field_cfg, is_new=is_new))

            tab["sections"].append(section)

        tabs.append(tab)

    return tabs


def get_display_name_from_parts(first_name="", middle_name="", last_name=""):
    return " ".join(
        part.strip()
        for part in [first_name or "", middle_name or "", last_name or ""]
        if part and part.strip()
    )


def get_first_name_value(payload):
    return payload.get("name1") or payload.get("first_name") or ""


def set_full_name_from_parts(doc, payload):
    first_name = get_first_name_value(payload)
    middle_name = payload.get("middle_name") or ""
    last_name = payload.get("last_name") or ""

    full_name = get_display_name_from_parts(first_name, middle_name, last_name)

    if full_name and doc.meta.has_field("full_name"):
        doc.full_name = full_name

    if first_name:
        if doc.meta.has_field("name1"):
            doc.name1 = first_name
        if doc.meta.has_field("first_name"):
            doc.first_name = first_name

    if middle_name and doc.meta.has_field("middle_name"):
        doc.middle_name = middle_name

    if last_name and doc.meta.has_field("last_name"):
        doc.last_name = last_name


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

    linked_contact = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Contact",
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
        pluck="parent",
        limit_page_length=1,
    )

    if linked_contact:
        return frappe.db.get_value(
            "Contact",
            linked_contact[0],
            ["name", "full_name", "first_name", "last_name", "email_id", "mobile_no", "phone"],
            as_dict=True,
        )

    return None


def get_or_create_contact_for_customer(customer_name):
    if not customer_name:
        return None

    existing = find_contact_for_customer(customer_name)
    if existing:
        return existing

    if not frappe.db.exists("Customer", customer_name):
        return None

    customer_fields = ["name", "customer_name"]

    customer_meta = frappe.get_meta("Customer")
    
    for fieldname in ["email_id", "mobile_no", "phone"]:
        if customer_meta.has_field(fieldname):
            customer_fields.append(fieldname)
    
    customer = frappe.db.get_value(
        "Customer",
        customer_name,
        customer_fields,
        as_dict=True,
    ) or {}

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
        ["name", "full_name", "first_name", "last_name", "email_id", "mobile_no", "phone"],
        as_dict=True,
    )


def sync_billing_contact_to_client_contacts(doc):
    customer_name = doc.get("billing_contact")
    if not customer_name:
        return

    if not doc.meta.has_field("client_contacts"):
        return

    contact = get_or_create_contact_for_customer(customer_name)
    if not contact:
        return

    contact_name = contact.get("name")
    if not contact_name:
        return

    for row in doc.get("client_contacts") or []:
        if row.get("contact") == contact_name:
            return

    child = doc.append("client_contacts", {})

    if child.meta.has_field("contact"):
        child.contact = contact_name

    if child.meta.has_field("contact_name"):
        child.contact_name = (
            contact.get("full_name")
            or " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")])).strip()
            or contact_name
        )

    if child.meta.has_field("phone"):
        child.phone = contact.get("mobile_no") or contact.get("phone") or ""

    if child.meta.has_field("email_id"):
        child.email_id = contact.get("email_id") or ""


def get_billing_contact(doc, contact_detail_base_url="/coach_db/contact_details"):
    customer_name = doc.get("billing_contact")

    if not customer_name:
        return None

    contact = get_or_create_contact_for_customer(customer_name)

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


@frappe.whitelist()
def get_client_contacts(client_name=None, contact_detail_base_url="/coach_db/contact_details"):
    require_logged_in_user()
    ensure_client_access(client_name)

    doc = frappe.get_doc("Client", client_name)
    contacts = []

    for row in doc.get("client_contacts") or []:
        contact_name = row.get("contact")
        contact_data = get_contact_data(contact_name)

        contacts.append(
            {
                "name": contact_name,
                "contact": contact_name,
                "display_name": row.get("contact_name") or contact_data.get("display_name") or contact_name or "Contact",
                "contact_name": row.get("contact_name") or contact_data.get("display_name") or contact_name or "Contact",
                "mobile": row.get("phone") or contact_data.get("phone") or "",
                "phone": row.get("phone") or contact_data.get("phone") or "",
                "email": row.get("email_id") or contact_data.get("email") or "",
                "company": contact_data.get("company") or "",
                "relationship": row.get("relationship") or row.get("relation") or "",
                "link": f"{contact_detail_base_url}?name={contact_name}" if contact_name else "",
            }
        )

    return contacts


def get_client_contacts_for_context(doc, contact_detail_base_url="/coach_db/contact_details"):
    if not doc or not doc.name:
        return []

    return get_client_contacts(doc.name, contact_detail_base_url)


def get_session_notes(doc):
    notes = []

    for row in doc.get("session_notes") or []:
        user = row.get("user") or row.get("owner") or row.get("created_by") or ""

        notes.append(
            {
                "session_date": row.get("session_date"),
                "session_type": row.get("session_type"),
                "notes": row.get("notes") or row.get("note") or row.get("note_text") or "",
                "note_text": row.get("notes") or row.get("note") or row.get("note_text") or "",
                "note_date": row.get("session_date"),
                "note_user": user,
                "note_user_name": frappe.get_cached_value("User", user, "full_name") or user,
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


@frappe.whitelist()
def link_existing_contact_to_client(client_name=None, contact_name=None, relationship_type=None, is_billing_contact=0):
    require_logged_in_user()
    ensure_client_access(client_name)

    client_name = (client_name or "").strip()
    contact_name = (contact_name or "").strip()
    relationship_type = (relationship_type or "").strip()
    is_billing_contact = int(is_billing_contact or 0)

    if not client_name or not frappe.db.exists("Client", client_name):
        frappe.throw(_("Client not found."))

    if not contact_name or not frappe.db.exists("Contact", contact_name):
        frappe.throw(_("Contact not found."))

    client = frappe.get_doc("Client", client_name)
    contact = frappe.get_doc("Contact", contact_name)

    existing_row = None

    for row in client.get("client_contacts") or []:
        if row.get("contact") == contact.name:
            existing_row = row
            break

    if not existing_row:
        existing_row = client.append("client_contacts", {})

    existing_row.contact = contact.name
    existing_row.contact_name = (
        contact.get("full_name")
        or " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")])).strip()
        or contact.name
    )
    existing_row.email_id = contact.get("email_id") or ""
    existing_row.phone = contact.get("mobile_no") or contact.get("phone") or ""
    existing_row.relationship_type = relationship_type
    existing_row.is_billing_contact = is_billing_contact

    if is_billing_contact:
        if not contact.get("custom_customer"):
            customer_doc = frappe.new_doc("Customer")
            customer_doc.customer_type = "Individual"
            customer_doc.customer_name = (
                contact.get("full_name")
                or " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")])).strip()
                or contact.get("company_name")
                or contact.get("email_id")
                or contact.name
            )
            customer_doc.save(ignore_permissions=True)

            contact.custom_customer = customer_doc.name

            if contact.meta.has_field("is_billing_contact"):
                contact.is_billing_contact = 1

            contact.append("links", {
                "link_doctype": "Customer",
                "link_name": customer_doc.name,
            })

            contact.save(ignore_permissions=True)

        existing_row.customer = contact.get("custom_customer") or ""
        client.billing_contact = contact.get("custom_customer") or ""

    client.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def get_client_notes(client_name):
    require_logged_in_user()
    ensure_client_access(client_name)

    doc = frappe.get_doc("Client", client_name)
    return get_session_notes(doc)


def is_cancelled_status(status):
    return normalize(status) in {
        "cancelled",
        "canceled",
        "cancelled by client",
        "cancelled by coach",
        "cancelled by session worker",
    }


def should_show_appointment_status(status):
    value = normalize(status)

    if not value:
        return True

    return not is_cancelled_status(value)


def get_effective_event_session_type(event_row):
    value = (event_row.get("custom_session_type") or "").strip()

    if value:
        return value

    template_name = (event_row.get("custom_appointment_type") or "").strip()

    if template_name and frappe.db.exists("Appointment Template", template_name):
        template_doc = frappe.get_doc("Appointment Template", template_name)

        for fieldname in ["appointment_type", "title", "template_name", "name"]:
            template_value = (template_doc.get(fieldname) or "").strip()
            if template_value:
                return template_value

    return event_row.get("subject") or "General"


def get_event_status(event_row):
    for fieldname in [
        "custom_appointment_status",
        "appointment_status",
        "status",
    ]:
        value = event_row.get(fieldname)
        if value:
            return value

    return "Open"


def map_event_status_to_ui(raw_status):
    mapping = {
        "Scheduled": "Booked",
        "Open": "Booked",
        "Booked": "Booked",
        "Draft": "Booked",
        "Attended": "Attended",
        "Completed": "Attended",
        "Cancelled": "Cancelled",
        "Canceled": "Cancelled",
        "No Show": "No Show",
        "Closed": "No Show",
    }

    return mapping.get((raw_status or "").strip(), raw_status or "Booked")


def get_progress_text(progress_text=None, session_number=None, total_sessions=None):
    progress_text = (progress_text or "").strip()

    if progress_text:
        if progress_text.lower().startswith("session "):
            return progress_text
        return f"Session {progress_text}"

    try:
        session_number = int(session_number or 0)
        total_sessions = int(total_sessions or 0)
    except Exception:
        session_number = 0
        total_sessions = 0

    if session_number and total_sessions:
        return f"Session {session_number}/{total_sessions}"

    return "—"


def get_event_client_appointments(client_name, calendar_detail_base_url="/coach_db/calendar_details"):
    if not frappe.db.exists("DocType", "Event"):
        return None

    event_meta = frappe.get_meta("Event")

    if not event_meta.has_field("custom_client"):
        return None

    fields = [
        "name",
        "subject",
        "starts_on",
        "ends_on",
        "location",
        "status",
    ]

    optional_fields = [
        "custom_client",
        "custom_session_type",
        "custom_appointment_type",
        "custom_appointment_status",
        "custom_billing_type",
        "custom_travel_charged",
        "appointment_status",
        "custom_session_number",
        "custom_total_sessions",
        "custom_progress_text",
        "custom_booking_warning",
    ]

    for fieldname in optional_fields:
        if event_meta.has_field(fieldname):
            fields.append(fieldname)

    rows = frappe.get_all(
        "Event",
        filters={"custom_client": client_name},
        fields=fields,
        order_by="starts_on desc",
        limit_page_length=500,
    )

    result = []

    for row in rows:
        raw_status = get_event_status(row)

        if not should_show_appointment_status(raw_status):
            continue

        row["appointment_start"] = row.get("starts_on")
        row["appointment_end"] = row.get("ends_on")
        row["display_status"] = map_event_status_to_ui(raw_status)
        row["ui_status"] = row["display_status"]
        row["display_progress"] = get_progress_text(
            row.get("custom_progress_text"),
            row.get("custom_session_number"),
            row.get("custom_total_sessions"),
        )
        row["item_display_name"] = get_effective_event_session_type(row)
        row["item"] = row["item_display_name"]
        row["appointment_type"] = row["item_display_name"]
        row["date"] = row.get("starts_on")
        row["time"] = ""
        row["view_link"] = f"{calendar_detail_base_url}?event={row.get('name')}"
        row["record_url"] = row["view_link"]
        result.append(row)

    return result


def get_item_display_name(item_code):
    if not item_code:
        return ""

    if frappe.db.exists("Item", item_code):
        item_name = frappe.db.get_value("Item", item_code, "item_name")
        return item_name or item_code

    return item_code


def get_client_appointment_rows(client_name, calendar_detail_base_url="/coach_db/calendar_details"):
    if not client_name or not frappe.db.exists("DocType", "Client Appointment"):
        return []

    rows = frappe.get_all(
        "Client Appointment",
        filters={"client": client_name},
        fields=[
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
        ],
        order_by="appointment_start desc, creation desc",
        limit_page_length=200,
    )

    result = []

    for row in rows:
        status = row.get("status") or ""
        linked_event_status = ""

        if row.get("linked_event") and frappe.db.exists("Event", row.get("linked_event")):
            linked_event_status = (
                frappe.db.get_value("Event", row.get("linked_event"), "custom_appointment_status")
                or frappe.db.get_value("Event", row.get("linked_event"), "appointment_status")
                or frappe.db.get_value("Event", row.get("linked_event"), "status")
                or ""
            )

        effective_status = linked_event_status or status

        if not should_show_appointment_status(effective_status):
            continue

        row["display_status"] = map_event_status_to_ui(effective_status)
        row["ui_status"] = row["display_status"]
        row["display_progress"] = get_progress_text(
            row.get("progress_text"),
            row.get("session_number"),
            row.get("total_sessions"),
        )
        row["item_display_name"] = get_item_display_name(row.get("item"))
        row["appointment_type"] = row["item_display_name"]
        row["date"] = row.get("appointment_start")
        row["time"] = ""

        row["location"] = frappe.db.get_value(
            "Event",
            row.get("linked_event"),
            "location"
        ) if row.get("linked_event") else ""

        row["view_link"] = (
            f"{calendar_detail_base_url}?event={row.get('linked_event')}"
            if row.get("linked_event")
            else ""
        )
        row["record_url"] = row["view_link"]

        result.append(row)

    return result


@frappe.whitelist()
def get_client_appointments(client_name, calendar_detail_base_url="/coach_db/calendar_details"):
    require_logged_in_user()
    ensure_client_access(client_name)

    if not client_name:
        return []

    appointment_rows = get_client_appointment_rows(client_name, calendar_detail_base_url)

    if appointment_rows:
        return appointment_rows

    event_rows = get_event_client_appointments(client_name, calendar_detail_base_url)
    if event_rows is not None:
        return event_rows

    return []


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


def get_link_display_fields(doctype):
    if not frappe.db.exists("DocType", doctype):
        return ["name"]

    meta = frappe.get_meta(doctype)
    fields = ["name"]

    for fieldname in [
        "coach_name",
        "sw_name",
        "session_worker_name",
        "full_name",
        "customer_name",
        "item_name",
        "title",
    ]:
        if meta.has_field(fieldname):
            fields.append(fieldname)

    return fields


@frappe.whitelist()
def get_link_options(doctype, txt=None, limit_page_length=500):
    require_logged_in_user()

    if not doctype or not frappe.db.exists("DocType", doctype):
        return []

    txt = (txt or "").strip().lower()
    fields = get_link_display_fields(doctype)

    rows = frappe.get_all(
        doctype,
        fields=fields,
        order_by="name asc",
        limit_page_length=int(limit_page_length or 500),
    )

    if not txt:
        return rows

    filtered = []

    for row in rows:
        haystack = " ".join(str(row.get(field) or "") for field in fields).lower()
        if txt in haystack:
            filtered.append(row)

    return filtered

def calculate_age_from_dob(date_of_birth):
    if not date_of_birth:
        return None

    dob = frappe.utils.getdate(date_of_birth)
    today = frappe.utils.getdate()

    age = today.year - dob.year

    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1

    return age


def get_client_type_from_age(age):
    if age is None:
        return ""

    if age < 12:
        return "Kid"
    if age < 18:
        return "Teen"
    if age <= 21:
        return "Uni Student"

    return "Adult"


def apply_age_and_client_type(doc):
    if not doc.meta.has_field("date_of_birth"):
        return

    dob = doc.get("date_of_birth")

    if not dob:
        if doc.meta.has_field("age"):
            doc.age = None
        return

    age = calculate_age_from_dob(dob)

    if doc.meta.has_field("age"):
        doc.age = age

    if doc.meta.has_field("client_type"):
        doc.client_type = get_client_type_from_age(age)


@frappe.whitelist()
def save_client(docname=None, data=None):
    require_logged_in_user()

    if docname:
        ensure_client_access(docname)

    payload = json.loads(data) if isinstance(data, str) else (data or {})
    is_new_client = not bool(docname)

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
        and (not df.read_only or df.fieldname in FORCE_EDITABLE_FIELDS or (is_new_client and df.fieldname == "full_name"))
        and df.fieldtype not in SKIP_FIELDTYPES
    }

    for fieldname, df in editable_fields.items():
        if fieldname not in payload:
            continue

        if fieldname == "full_name" and not is_new_client:
            continue

        value = payload.get(fieldname)

        if df.fieldtype == "Check":
            value = 1 if str(value).lower() in ("1", "true", "yes", "on") else 0

        if df.fieldtype in ("Float", "Currency", "Percent"):
            value = float(value or 0)

        if df.fieldtype == "Int":
            value = int(float(value or 0))

        doc.set(fieldname, value)

    if is_new_client:
        set_full_name_from_parts(doc, payload)
    
    apply_age_and_client_type(doc)
    
    sync_billing_contact_to_client_contacts(doc)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"name": doc.name}


@frappe.whitelist()
def add_client_note(client_name, note_text, session_date=None, session_type=None):
    require_logged_in_user()
    ensure_client_access(client_name)

    note_text = (note_text or "").strip()

    if not note_text:
        frappe.throw(_("Note text is required."))

    doc = frappe.get_doc("Client", client_name)

    if not doc.meta.has_field("session_notes"):
        frappe.throw(_("No session notes child table was found on Client."))

    # Fix any existing note rows missing mandatory client field
    for existing_child in doc.get("session_notes") or []:
        if existing_child.meta.has_field("client") and not existing_child.get("client"):
            existing_child.client = doc.name

    child = doc.append("session_notes", {})

    if child.meta.has_field("client"):
        child.client = doc.name

    if child.meta.has_field("notes"):
        child.notes = note_text
    elif child.meta.has_field("note"):
        child.note = note_text
    elif child.meta.has_field("note_text"):
        child.note_text = note_text

    if child.meta.has_field("session_date"):
        child.session_date = session_date or frappe.utils.nowdate()

    if child.meta.has_field("session_type") and session_type:
        child.session_type = session_type

    if child.meta.has_field("user"):
        child.user = frappe.session.user

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "message": _("Note added successfully.")}
    
def get_client_context_data(client_name=None, is_new=False, base_url="/coach_db", enforce_access=True):
    require_logged_in_user()

    if client_name and not is_new and enforce_access:
        ensure_client_access(client_name)

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
        "tabs": build_tabs(doc, is_new=bool(is_new or not is_existing_client)),
        "billing_contact": get_billing_contact(doc, f"{base_url}/contact_details"),
        "client_contacts": get_client_contacts_for_context(doc, f"{base_url}/contact_details"),
        "session_notes": get_session_notes(doc),
        "client_appointments": get_client_appointments(
            doc.name if is_existing_client else "",
            f"{base_url}/calendar_details",
        ) if is_existing_client else [],
        "package_balances": get_package_balances(doc.name if is_existing_client else ""),
        "client_invoices": get_client_invoices(doc.name if is_existing_client else ""),
        "travel_charged": int(doc.get("travel_charged") or 0),
        "travel_miles_one_way": doc.get("travel_miles_one_way") or 0,
    }


def get_client_for_context(client_name):
    ensure_client_access(client_name)
    return frappe.get_doc("Client", client_name)

"""
Franchisor-only report: a flat list of clients (optionally scoped to
one coach, same or_filters={"primary_coach": ..., "attending_coach": ...}
pattern as client_locations.py) with the fields Ashley asked for -
client name, billing contact name, age, client type, billing contact
email, billing contact phone number, sex and gender identity. Which
columns actually show/export is the frontend's choice (client_list_
report.js) - this always returns every field, every row.

Client's own field names aren't fixed by this repo's schema (Client
isn't a doctype this app ships), so name/sex/gender are resolved
defensively the same "candidates" way client_details.py's own address
section does. Client.billing_contact is a Link to Customer, not
directly to Contact - find_contact_for_customer() is client_details.py's
own READ-ONLY lookup for the Contact actually linked to that Customer;
deliberately NOT get_or_create_contact_for_customer(), which can create
a new Contact as a side effect - a report just being viewed should
never silently create data.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in, is_franchisor_user
from dashboard.api.shared.client_details import field_meta_lookup, find_field, calculate_age_from_dob, find_contact_for_customer, get_client_type_from_age
from dashboard.api.shared.clients import get_coach_label, build_display_name

_SEX_FIELD_CFG = {"label": "Sex", "candidates": ["sex"]}
_GENDER_FIELD_CFG = {"label": "Gender Identity", "candidates": ["gender_identity", "gender"]}


def _client_field(field_cfg):
    meta = frappe.get_meta("Client")
    by_label, by_fieldname = field_meta_lookup(meta)
    df = find_field(field_cfg, by_label, by_fieldname)
    return df.fieldname if df else None


@frappe.whitelist()
def get_client_list_report(coach=None, status=None):
    """
    status: "" (default) hides Archived clients, "All" shows every
    status, "Archived" shows only Archived ones - same convention
    clients.py's own list already uses (_apply_client_filter_args), so
    "no status picked" behaves identically between the two.
    """
    ensure_logged_in()

    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to view this report."), frappe.PermissionError)

    if not frappe.db.exists("DocType", "Client"):
        return {"rows": []}

    client_meta = frappe.get_meta("Client")
    sex_fieldname = _client_field(_SEX_FIELD_CFG)
    gender_fieldname = _client_field(_GENDER_FIELD_CFG)

    fields = ["name", "primary_coach", "attending_coach"]

    for candidate in ("full_name", "name1", "last_name", "preferred_name"):
        if client_meta.has_field(candidate) and candidate not in fields:
            fields.append(candidate)

    if client_meta.has_field("age"):
        fields.append("age")
    if client_meta.has_field("date_of_birth"):
        fields.append("date_of_birth")
    if client_meta.has_field("billing_contact"):
        fields.append("billing_contact")
    if client_meta.has_field("client_type"):
        fields.append("client_type")
    if sex_fieldname:
        fields.append(sex_fieldname)
    if gender_fieldname:
        fields.append(gender_fieldname)

    coach = (coach or "").strip()
    status = (status or "").strip()

    filters = []
    if client_meta.has_field("status"):
        if not status:
            filters.append(["status", "!=", "Archived"])
        elif status != "All":
            filters.append(["status", "=", status])

    or_filters = {"primary_coach": coach, "attending_coach": coach} if coach else None

    rows = frappe.get_all(
        "Client",
        fields=fields,
        filters=filters,
        or_filters=or_filters,
        limit_page_length=5000,
        ignore_permissions=True,
    )

    # Cache per Customer (billing_contact) so two clients billed to the
    # same contact don't look it up twice.
    contact_by_customer = {}

    out = []
    for row in rows:
        coach_name = row.get("primary_coach") or row.get("attending_coach")

        billing_contact_name = ""
        billing_contact_email = ""
        billing_contact_phone = ""

        customer_name = row.get("billing_contact")
        if customer_name:
            if customer_name not in contact_by_customer:
                contact_by_customer[customer_name] = find_contact_for_customer(customer_name)

            contact = contact_by_customer[customer_name]
            if contact:
                billing_contact_name = (
                    contact.get("full_name")
                    or " ".join(filter(None, [contact.get("first_name"), contact.get("last_name")])).strip()
                    or contact.get("name")
                )
                billing_contact_email = contact.get("email_id") or ""
                billing_contact_phone = contact.get("mobile_no") or contact.get("phone") or ""

        age = row.get("age")
        if not age and row.get("date_of_birth"):
            age = calculate_age_from_dob(row.get("date_of_birth"))

        client_type = row.get("client_type") or get_client_type_from_age(age)

        out.append({
            "client": row.name,
            "client_label": build_display_name(row),
            "coach_label": get_coach_label(coach_name),
            "billing_contact_label": billing_contact_name,
            "age": age or "",
            "client_type": client_type or "",
            "billing_contact_email": billing_contact_email,
            "billing_contact_phone": billing_contact_phone,
            "sex": (row.get(sex_fieldname) or "") if sex_fieldname else "",
            "gender": (row.get(gender_fieldname) or "") if gender_fieldname else "",
        })

    out.sort(key=lambda r: (r.get("client_label") or "").lower())

    return {"rows": out}

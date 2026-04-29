import frappe
from frappe import _

from dashboard.api.shared.permissions import (
    ensure_office_user,
    ensure_franchisor_can_access_session_worker,
    ensure_franchisor_can_access_coach,
)


SESSION_WORKER_DOCTYPE = "Session Worker"
COACH_DOCTYPE = "Coach"


SESSION_WORKER_FIELDS = [
    "sw_name",
    "first_name",
    "middle_name",
    "last_name",
    "user",
    "sw_email",
    "phone",
    "birth_date",
    "gender",
    "location",
    "photo",
    "bio",
    "interest",
    "bank_name",
    "account_holder_name",
    "account_number",
    "sort_code",
    "1_on_1_session_rate",
    "group_session_rate",
    "workshop_session_rate",
    "travel_rate_per_mile",
    "invoice_frequency",
    "invoice_cycle_start_date",
]

COACH_FIELDS = [
    "coach_name",
    "user",
    "coach_email",
    "photo",
    "bio",
    "bank_account",
    "company",
    "pricelist",
    "insurance_received_date",
    "insurance_expiry_date",
    "insurance_number",
]


@frappe.whitelist()
def get_session_workers():
    ensure_office_user()

    return frappe.get_all(
        SESSION_WORKER_DOCTYPE,
        fields=[
            "name",
            "sw_name",
            "sw_email",
            "phone",
            "location",
        ],
        order_by="sw_name asc",
        limit_page_length=1000,
    )


@frappe.whitelist()
def get_coaches():
    ensure_office_user()

    return frappe.get_all(
        COACH_DOCTYPE,
        fields=[
            "name",
            "coach_name",
            "coach_email",
            "company",
            "bank_account",
        ],
        order_by="coach_name asc",
        limit_page_length=1000,
    )


@frappe.whitelist()
def update_session_worker(session_worker_name):
    doc = ensure_franchisor_can_access_session_worker(session_worker_name)

    for fieldname in SESSION_WORKER_FIELDS:
        if doc.meta.has_field(fieldname):
            value = frappe.form_dict.get(fieldname)
            if value is not None:
                doc.set(fieldname, value)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "message": _("Session Worker updated successfully."),
    }


@frappe.whitelist()
def update_coach(coach_name):
    doc = ensure_franchisor_can_access_coach(coach_name)

    for fieldname in COACH_FIELDS:
        if doc.meta.has_field(fieldname):
            value = frappe.form_dict.get(fieldname)
            if value is not None:
                doc.set(fieldname, value)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "message": _("Coach updated successfully."),
    }

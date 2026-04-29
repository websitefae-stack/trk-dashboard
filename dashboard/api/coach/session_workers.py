import frappe
from frappe import _

from dashboard.api.shared.permissions import (
    get_current_coach,
    ensure_coach_can_access_session_worker,
)


SESSION_WORKER_DOCTYPE = "Session Worker"


PROFILE_FIELDS = [
    "first_name",
    "middle_name",
    "last_name",
    "phone",
    "gender",
    "location",
    "bio",
    "interest",
]

BANKING_FIELDS = [
    "bank_name",
    "account_holder_name",
    "account_number",
    "sort_code",
]

RATE_FIELDS = [
    "1_on_1_session_rate",
    "group_session_rate",
    "workshop_session_rate",
    "travel_rate_per_mile",
    "invoice_frequency",
    "invoice_cycle_start_date",
]


def get_linked_session_workers():
    coach = get_current_coach()

    rows = frappe.get_all(
        SESSION_WORKER_DOCTYPE,
        fields=[
            "name",
            "sw_name",
            "sw_email",
            "phone",
            "location",
            "photo",
        ],
        order_by="sw_name asc",
        limit_page_length=500,
    )

    allowed = []

    for row in rows:
        doc = frappe.get_doc(SESSION_WORKER_DOCTYPE, row.name)

        for link in doc.get("linked_coaches") or []:
            if link.get("is_active") and link.get("coach") == coach.name:
                allowed.append(row)
                break

    return allowed


@frappe.whitelist()
def update_linked_session_worker(session_worker_name):
    session_worker = ensure_coach_can_access_session_worker(session_worker_name)

    editable_fields = PROFILE_FIELDS + BANKING_FIELDS + RATE_FIELDS

    for fieldname in editable_fields:
        if session_worker.meta.has_field(fieldname):
            session_worker.set(fieldname, frappe.form_dict.get(fieldname))

    session_worker.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "message": _("Session Worker updated successfully."),
    }

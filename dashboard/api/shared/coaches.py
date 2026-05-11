import frappe

from dashboard.api.shared.permissions import (
    COACH_DOCTYPE,
    ensure_office_user,
)


COACH_LIST_FIELDS = [
    "name",
    "coach_name",
    "user",
    "coach_email",
    "company",
    "bank_account",
    "pricelist",
    "insurance_received_date",
    "insurance_expiry_date",
    "insurance_number",
]


def get_coach_display_name(coach):
    return (
        coach.get("coach_name")
        or coach.get("name")
        or "Unnamed Coach"
    )


def normalize_coach_row(coach):
    return {
        "name": coach.get("name"),
        "coach_name": coach.get("coach_name") or "",
        "display_name": get_coach_display_name(coach),
        "user": coach.get("user") or "",
        "coach_email": coach.get("coach_email") or "",
        "company": coach.get("company") or "",
        "bank_account": coach.get("bank_account") or "",
        "pricelist": coach.get("pricelist") or "",
        "insurance_received_date": coach.get("insurance_received_date") or "",
        "insurance_expiry_date": coach.get("insurance_expiry_date") or "",
        "insurance_number": coach.get("insurance_number") or "",
    }


@frappe.whitelist()
def get_coaches():
    ensure_office_user()

    coaches = frappe.get_all(
        COACH_DOCTYPE,
        fields=COACH_LIST_FIELDS,
        order_by="coach_name asc",
        limit_page_length=5000,
    )

    return [normalize_coach_row(coach) for coach in coaches]

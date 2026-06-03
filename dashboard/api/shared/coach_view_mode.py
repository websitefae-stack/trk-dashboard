import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard


def get_coach_view_mode(scope=None, coach_name=None):
    scope = (scope or "").strip()
    coach_name = (coach_name or "").strip()

    if not coach_name:
        return {
            "is_view_mode": 0,
            "query_string": "",
            "return_to": "",
            "view_coach_name": "",
            "view_coach_display_name": "",
        }

    if scope != "franchisor":
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    if not frappe.db.exists("Coach", coach_name):
        frappe.throw(_("Coach not found."))

    coach_display_name = (
        frappe.db.get_value("Coach", coach_name, "coach_name")
        or coach_name
    )

    return_to = frappe.form_dict.get("return_to") or "/franchisor_db/coaches"

    query_string = (
        "?view_as="
        + frappe.utils.quote(coach_name)
        + "&viewer=franchisor"
        + "&return_to="
        + frappe.utils.quote(return_to)
    )

    return {
        "is_view_mode": 1,
        "query_string": query_string,
        "return_to": return_to,
        "view_coach_name": coach_name,
        "view_coach_display_name": coach_display_name,
    }

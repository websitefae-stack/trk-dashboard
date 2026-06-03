import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.contacts import (
    get_contacts_for_scope,
    get_current_coach_name,
)
from dashboard.api.shared.coach_view_mode import get_coach_view_mode


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    view_as = frappe.form_dict.get("view_as")
    viewer = frappe.form_dict.get("viewer")

    view_mode = get_coach_view_mode(
        scope=viewer,
        coach_name=view_as,
    )

    context.no_cache = 1
    context.page_title = "Contacts"
    context.active_page = "contacts"
    context.dashboard_notifications_url = "/coach_db/notifications"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
        context.contacts = get_contacts_for_view_coach(view_mode.get("view_coach_name"))
    else:
        redirect_if_wrong_dashboard("coach")

        context.dashboard_user_name = frappe.db.get_value(
            "Coach",
            get_current_coach_name(),
            "coach_name",
        ) or frappe.session.user

        context.contacts = get_contacts_for_scope("coach")


def get_contacts_for_view_coach(coach_name):
    if not coach_name:
        return []

    rows = frappe.get_all(
        "Contact",
        filters={
            "custom_coach": coach_name,
        },
        fields=[
            "name",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "email_id",
            "mobile_no",
            "phone",
        ],
        order_by="full_name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )

    contacts = []

    for row in rows:
        contacts.append({
            "name": row.name,
            "display_name": row.full_name or " ".join(
                part for part in [row.first_name, row.middle_name, row.last_name] if part
            ) or row.name,
            "full_name": row.full_name,
            "email": row.email_id,
            "mobile": row.mobile_no or row.phone,
        })

    return contacts

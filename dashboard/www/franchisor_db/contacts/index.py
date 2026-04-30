import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.contacts import get_contacts_for_scope, get_current_coach_name
from dashboard.api.franchisor.clients import get_coaches


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    redirect_if_wrong_dashboard("franchisor")

    contact_scope = frappe.form_dict.get("contact_scope") or "my"

    context.no_cache = 1
    context.page_title = "Contacts"
    context.active_page = "contacts"
    context.contact_scope = contact_scope
    context.my_coach_name = get_current_coach_name()
    context.my_coach_display_name = frappe.db.get_value(
        "Coach",
        context.my_coach_name,
        "coach_name",
    ) or "My contacts"
    context.coaches = get_coaches()
    context.contacts = get_contacts_for_scope(
        "franchisor",
        show_all=False,
        coach_scope=contact_scope,
    )

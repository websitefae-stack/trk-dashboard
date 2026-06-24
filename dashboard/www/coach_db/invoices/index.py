import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared import invoices as invoice_api
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
    context.page_title = "Invoices"
    context.active_page = "invoices"
    context.dashboard_base_path = "/coach_db"
    context.dashboard_notifications_url = "/coach_db/notifications" + (view_mode.get("query_string") or "")

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        selected_coach = view_mode.get("view_coach_name")
        context.dashboard_user_name = context.coach_view_display_name

        context.invoices = get_invoices_for_view_coach(
            selected_coach,
            context.coach_view_query,
        )

        context.coach_options = []
        context.selected_coach = selected_coach
        context.current_coach = selected_coach
        context.current_coach_label = get_coach_label(selected_coach)
        context.current_company = ""
        context.is_franchisor = 1

    else:
        redirect_if_wrong_dashboard("coach")

        selected_coach = (frappe.form_dict.get("coach") or "").strip()

        data = invoice_api.get_invoice_page_data(
            dashboard_type="coach",
            selected_coach=selected_coach,
        )

        context.invoices = data.get("invoices", [])
        context.pagination = data.get("pagination", {})
        context.search = data.get("search", "")
        context.coach_options = data.get("coach_options", [])
        context.selected_coach = data.get("selected_coach", "")
        context.current_coach = data.get("current_coach", "")
        context.current_coach_label = data.get("current_coach_label", "")
        context.current_company = data.get("current_company", "")
        context.is_franchisor = 0


def get_invoices_for_view_coach(coach_name, coach_view_query=""):
    coach_name = (coach_name or "").strip()

    if not coach_name:
        return []

    client_rows = get_clients_for_view_coach(coach_name)
    client_names = [row.get("name") for row in client_rows if row.get("name")]

    if not client_names:
        return []

    invoice_rows = frappe.get_all(
        "Sales Invoice",
        filters={
            "custom_client": ["in", client_names],
            "docstatus": ["!=", 2],
        },
        fields=invoice_api._get_invoice_fields(),
        order_by="posting_date desc, modified desc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    client_map = {row.get("name"): row for row in client_rows if row.get("name")}

    rows = []

    for invoice in invoice_rows:
        row = invoice_api._normalise_invoice_row(
            invoice,
            client_map,
            invoice_api.COACH_DASHBOARD,
        )

        row["details_url"] = (
            "/coach_db/invoice_details?name="
            + frappe.utils.quote(row.get("name") or "")
            + (coach_view_query.replace("?", "&") if coach_view_query else "")
        )

        rows.append(row)

    return rows


def get_clients_for_view_coach(coach_name):
    rows_by_name = {}

    for row in frappe.get_all(
        "Client",
        filters={"primary_coach": coach_name},
        fields=invoice_api._get_client_fields(),
        limit_page_length=5000,
        ignore_permissions=True,
    ):
        rows_by_name[row.name] = row

    for row in frappe.get_all(
        "Client",
        filters={"attending_coach": coach_name},
        fields=invoice_api._get_client_fields(),
        limit_page_length=5000,
        ignore_permissions=True,
    ):
        rows_by_name[row.name] = row

    return list(rows_by_name.values())


def get_coach_label(coach_name):
    if not coach_name:
        return ""

    if not frappe.db.exists("Coach", coach_name):
        return coach_name

    return frappe.db.get_value("Coach", coach_name, "coach_name") or coach_name

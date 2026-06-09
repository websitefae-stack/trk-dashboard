import frappe
from frappe import _

from dashboard.api.shared.permissions import redirect_if_wrong_dashboard
from dashboard.api.shared.directory import get_coach_display_name
from dashboard.api.shared.session_workers import get_session_workers
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
    context.page_title = "Session Workers"
    context.active_page = "session_workers"
    context.dashboard_notifications_url = "/coach_db/notifications" + (view_mode.get("query_string") or "")
    context.dashboard_base_url = "/coach_db"

    context.coach_view_mode = view_mode
    context.coach_view_query = view_mode.get("query_string") or ""
    context.coach_is_view_mode = view_mode.get("is_view_mode") or 0
    context.coach_view_return_to = view_mode.get("return_to") or ""
    context.coach_view_display_name = view_mode.get("view_coach_display_name") or ""

    if context.coach_is_view_mode:
        context.dashboard_user_name = context.coach_view_display_name
        context.session_workers = get_session_workers_for_view_coach(
            view_mode.get("view_coach_name"),
            context.coach_view_query,
        )
    else:
        redirect_if_wrong_dashboard("coach")
        context.dashboard_user_name = get_coach_display_name()
        data = get_session_workers(scope="coach")
        context.session_workers = add_session_worker_dashboard_urls(
            data.get("session_workers") or [],
            "",
        )


def get_session_workers_for_view_coach(coach_name, coach_view_query=""):
    coach_name = (coach_name or "").strip()

    if not coach_name:
        return []

    client_rows = frappe.get_all(
        "Client",
        filters=[
            ["Client", "primary_coach", "=", coach_name],
            "or",
            ["Client", "attending_coach", "=", coach_name],
        ],
        fields=[
            "name",
            "full_name",
            "name1",
            "last_name",
            "primary_coach",
            "attending_coach",
            "session_worker",
        ],
        limit_page_length=5000,
        ignore_permissions=True,
    )

    worker_to_clients = {}

    for client in client_rows:
        worker_name = client.get("session_worker")

        if not worker_name:
            continue

        if worker_name not in worker_to_clients:
            worker_to_clients[worker_name] = []

        worker_to_clients[worker_name].append(client)

    worker_names = sorted(worker_to_clients.keys())

    if not worker_names:
        return []

    rows = frappe.get_all(
        "Session Worker",
        filters={"name": ["in", worker_names]},
        fields=[
            "name",
            "sw_name",
            "sw_email",
            "phone",
        ],
        order_by="sw_name asc, name asc",
        limit_page_length=5000,
        ignore_permissions=True,
    )

    workers = []

    for row in rows:
        linked_clients = worker_to_clients.get(row.name) or []

        workers.append({
            "name": row.name,
            "display_name": row.get("sw_name") or row.name,
            "sw_name": row.get("sw_name") or "",
            "email": row.get("sw_email") or "",
            "mobile": row.get("phone") or "",
            "phone": row.get("phone") or "",
            "linked_clients": linked_clients,
            "linked_clients_count": len(linked_clients),
            "linked_coach_label": context_safe_coach_label(coach_name),
        })

    return add_session_worker_dashboard_urls(workers, coach_view_query)


def add_session_worker_dashboard_urls(workers, coach_view_query=""):
    for worker in workers:
        worker_name = worker.get("name") or ""

        return_to = "/coach_db/session_workers" + (coach_view_query or "")

        worker["session_worker_dashboard_url"] = (
            "/session_worker_db"
            + "?view_as="
            + frappe.utils.quote(worker_name)
            + "&viewer=franchisor"
            + "&return_to="
            + frappe.utils.quote(return_to)
        )

    return workers


def context_safe_coach_label(coach_name):
    if not coach_name:
        return ""

    if not frappe.db.exists("Coach", coach_name):
        return coach_name

    return frappe.db.get_value("Coach", coach_name, "coach_name") or coach_name

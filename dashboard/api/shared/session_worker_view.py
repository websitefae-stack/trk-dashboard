import frappe
from frappe import _

from dashboard.api.shared.session_workers import get_session_workers
from dashboard.api.shared.dashboard import (
    SESSION_WORKER_DASHBOARD,
    _get_period_ranges,
    _count_billing_type,
    _sum_travel_miles,
    _get_upcoming_appointments,
)


def ensure_can_view_session_worker(scope, worker_name):
    scope = (scope or "").strip().lower()
    worker_name = (worker_name or "").strip()

    if scope not in ["coach", "franchisor"]:
        frappe.throw(_("Invalid session worker view scope."), frappe.PermissionError)

    if not worker_name:
        frappe.throw(_("Session Worker not found."))

    data = get_session_workers(scope=scope)
    workers = data.get("session_workers") or []

    for worker in workers:
        if worker.get("name") == worker_name:
            return worker

    frappe.throw(
        _("You do not have permission to view this session worker."),
        frappe.PermissionError,
    )


def get_session_worker_invoice_settings(worker_name):
    invoice_frequency = "Monthly"
    invoice_cycle_start_date = None

    if worker_name and frappe.db.exists("Session Worker", worker_name):
        worker_doc = frappe.get_doc("Session Worker", worker_name)
        meta = frappe.get_meta(worker_doc.doctype)

        if meta.has_field("invoice_frequency"):
            invoice_frequency = (worker_doc.get("invoice_frequency") or "Monthly").strip()

        if meta.has_field("invoice_cycle_start_date"):
            invoice_cycle_start_date = worker_doc.get("invoice_cycle_start_date")

    return invoice_frequency, invoice_cycle_start_date


def build_view_context(scope, worker):
    return {
        "user": frappe.session.user,
        "worker_doctype": "Session Worker",
        "worker_name": worker.get("name"),
        "worker_label": worker.get("display_name") or worker.get("name"),
        "resolution_note": "Read-only session worker view from " + scope + " dashboard.",
        "is_dashboard_admin": False,
        "is_read_only_view": True,
        "view_scope": scope,
    }


def get_session_worker_dashboard_summary(scope=None, worker_name=None):
    worker = ensure_can_view_session_worker(scope, worker_name)
    context = build_view_context(scope, worker)

    invoice_frequency, invoice_cycle_start_date = get_session_worker_invoice_settings(worker.get("name"))
    period = _get_period_ranges(invoice_frequency, invoice_cycle_start_date)

    return {
        "dashboard_type": SESSION_WORKER_DASHBOARD,
        "session_worker_name": worker.get("display_name") or worker.get("name"),
        "session_worker_docname": worker.get("name") or "",
        "invoice_frequency": invoice_frequency,
        "previous_label": period["previous_label"],
        "current_label": period["current_label"],

        "one_to_one_previous": _count_billing_type(
            context, "One to One", period["previous_start"], period["previous_end"]
        ),
        "one_to_one_current": _count_billing_type(
            context, "One to One", period["current_start"], period["current_end"]
        ),

        "group_previous": _count_billing_type(
            context, "Group", period["previous_start"], period["previous_end"]
        ),
        "group_current": _count_billing_type(
            context, "Group", period["current_start"], period["current_end"]
        ),

        "workshop_previous": _count_billing_type(
            context, "Workshop", period["previous_start"], period["previous_end"]
        ),
        "workshop_current": _count_billing_type(
            context, "Workshop", period["current_start"], period["current_end"]
        ),

        "travel_miles_previous": _sum_travel_miles(
            context, period["previous_start"], period["previous_end"]
        ),
        "travel_miles_current": _sum_travel_miles(
            context, period["current_start"], period["current_end"]
        ),

        "upcoming_appointments": _get_upcoming_appointments(
            SESSION_WORKER_DASHBOARD,
            context,
            limit=8,
        ),
    }

import frappe

from dashboard.api.shared.session_workers import get_session_workers


def get_context(context):
    context.no_cache = 1
    context.title = "Session Workers"
    context.dashboard_scope = "coach"

    data = get_session_workers(scope="coach")

    context.session_worker_context = data
    context.session_workers = data.get("session_workers") or []
    context.current_coach = data.get("current_coach") or ""
    context.current_coach_label = data.get("current_coach_label") or ""

    return context

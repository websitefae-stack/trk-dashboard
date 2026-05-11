import frappe

from dashboard.api.shared.session_workers import get_session_workers


def get_context(context):
    context.no_cache = 1
    context.title = "Session Workers"
    context.dashboard_scope = "franchisor"

    data = get_session_workers(scope="franchisor")

    context.session_worker_context = data
    context.session_workers = data.get("session_workers") or []
    context.current_coach = data.get("current_coach") or ""
    context.current_coach_label = data.get("current_coach_label") or ""

    coach_options = {}

    for worker in context.session_workers:
        for coach in worker.get("linked_coaches") or []:
            if coach.get("name"):
                coach_options[coach.get("name")] = coach.get("display_name") or coach.get("name")

    context.coach_filter_options = [
        {
            "name": name,
            "display_name": label,
        }
        for name, label in sorted(coach_options.items(), key=lambda item: item[1].lower())
    ]

    return context

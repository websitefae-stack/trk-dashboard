from dashboard.api.coach.clients import get_coach_display_name
from dashboard.www.trk_dashboard.client_details.index import get_context as coach_client_details_context


def get_context(context):
    return coach_client_details_context(context)

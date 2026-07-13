app_name = "dashboard"
app_title = "The Resilient Dashboard"
app_publisher = "The Resilient Kid"
app_description = "Multi-role dashboard system for Session Workers, Coaches, and Franchisors"
app_email = "support@theresilientkid.uk"
app_license = "MIT"

web_include_css = [
    "/assets/dashboard/css/shared/reset.css",
    "/assets/dashboard/css/shared/layout.css",
    "/assets/dashboard/css/shared/topbar.css",
    "/assets/dashboard/css/shared/navigation.css",
    "/assets/dashboard/css/shared/buttons.css",
    "/assets/dashboard/css/shared/cards.css",
    "/assets/dashboard/css/shared/forms.css",
    "/assets/dashboard/css/shared/tables.css",
    "/assets/dashboard/css/shared/badges.css",
    "/assets/dashboard/css/shared/details.css",
    "/assets/dashboard/css/shared/notifications.css",
    "/assets/dashboard/css/shared/mobile.css",
]

web_include_js = [
    "/assets/dashboard/js/shared/dashboard_sidebar.js",
    "/assets/dashboard/js/shared/pagination.js",
]

website_context = {
    "favicon": "/assets/dashboard/images/favicon.png",
    "splash_image": "/assets/dashboard/images/logo.png",
}

website_route_rules = []

fixtures = []

# Keep appointments Private (Frappe's own permission model then restricts
# visibility/reminders to the owner - coaches shouldn't see each other's
# sessions) while still giving HQ/office full visibility in the raw Frappe
# backend, via an explicit share rather than making events Public to
# everyone. share_event_with_admins() only enqueues a background job here -
# see its docstring for why doing the actual share synchronously previously
# broke saving appointments.
#
# recalculate_client_package_balance() is a ported version of the
# "Package Recalculate Balance" Server Script - see packages.py's module
# docstring. Disable/delete that Server Script once this is deployed so the
# same recalculation doesn't run twice on every appointment save.
doc_events = {
    "Event": {
        "after_insert": [
            "dashboard.api.shared.calendar.share_event_with_admins",
            "dashboard.api.shared.packages.recalculate_client_package_balance",
        ],
        "on_update": [
            "dashboard.api.shared.calendar.share_event_with_admins",
            "dashboard.api.shared.packages.recalculate_client_package_balance",
        ],
    },
    # Intake Doctype is the real "client intake" Web Form, built and owned
    # directly in Frappe Desk (not part of this app) - these fire on every
    # submission/edit to sync the answers onto the linked Client Lead. See
    # dashboard.api.shared.leads.sync_intake_doctype_submission.
    "Intake Doctype": {
        "after_insert": "dashboard.api.shared.leads.sync_intake_doctype_submission",
        "on_update": "dashboard.api.shared.leads.sync_intake_doctype_submission",
    },
}

# Safety net for the pending-booking queue (see pending_bookings.py) - picks
# up any Pending Booking whose background job never ran (e.g. the worker
# that would have processed it crashed first) instead of letting it sit
# there forever.
scheduler_events = {
    "cron": {
        "*/5 * * * *": [
            "dashboard.api.shared.pending_bookings.sweep_stuck_pending_bookings",
        ],
    }
}

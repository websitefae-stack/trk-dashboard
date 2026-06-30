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

fixtures = [
    {"dt": "Custom DocPerm", "filters": [["document_type", "in", ["Google Calendar"]]]},
]

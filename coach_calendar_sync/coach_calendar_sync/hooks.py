app_name = "coach_calendar_sync"
app_title = "Coach Calendar Sync"
app_publisher = "The Resilient Kid"
app_description = "Google Calendar sync for Coaches and Session Workers"
app_email = "support@theresilientkid.co.uk"
app_license = "MIT"

# DocType events
doc_events = {
    "Event": {
        "after_insert": "coach_calendar_sync.sync.event_hooks.after_insert",
        "on_update": "coach_calendar_sync.sync.event_hooks.on_update",
        "on_cancel": "coach_calendar_sync.sync.event_hooks.on_cancel",
        "on_trash": "coach_calendar_sync.sync.event_hooks.on_trash",
    }
}

# Scheduled tasks
scheduler_events = {
    "cron": {
        # Every 5 minutes
        "*/5 * * * *": [
            "coach_calendar_sync.sync.scheduler.run_sync_cycle",
        ]
    }
}

# Website routes
website_route_rules = [
    {"from_route": "/coach-calendar-sync/oauth/callback", "to_route": "coach_calendar_sync.api.oauth.callback"},
]

# Fixtures – export these so the app is self-contained
fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Coach Calendar Sync"]]},
    "Calendar Sync Settings",
]

after_install = "coach_calendar_sync.install.after_install"

# Client-side scripts attached to forms
doctype_js = {
    "Coach": ["public/js/google_calendar_form.js", "public/js/coach_form.js"],
    "Session Worker": ["public/js/google_calendar_form.js", "public/js/session_worker_form.js"],
}


# Whitelisted methods exposed to the frontend
# (individual methods use @frappe.whitelist() decorator)

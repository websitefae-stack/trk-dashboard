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
    "/assets/dashboard/css/shared/practice_documents.css",
    "/assets/dashboard/css/shared/mobile.css",
]

web_include_js = [
    "/assets/dashboard/js/shared/dashboard_sidebar.js?v=3",
    "/assets/dashboard/js/shared/pagination.js",
    # Site-wide so it also reaches Frappe Learning's lesson pages (a
    # separate app on this same site) - see the file's own docstring for
    # why this lives here rather than as a change to Learning itself.
    # Inert on every other page: it only ever acts on a share.descript.com
    # link, which nothing outside a lesson would ever contain.
    "/assets/dashboard/js/shared/descript_embed.js?v=1",
]

website_context = {
    "favicon": "/files/TRH - Favicon.png",
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
        # Deleting an appointment (calendar.delete_session(), or a raw
        # desk delete) used to leave its Client Appointment bookkeeping
        # record behind pointing at an Event that no longer exists, and
        # never told the Client Package Balance a session was freed up.
        # See packages.py's "Delete cascade" section.
        "on_trash": "dashboard.api.shared.packages.handle_event_trash",
    },
    # Same cascade in the other direction - deleting the bookkeeping
    # record directly (e.g. from the Frappe desk) must not leave its
    # Event stranded on the calendar.
    "Client Appointment": {
        "on_trash": "dashboard.api.shared.packages.handle_client_appointment_trash",
    },
    # Intake Doctype is the real "client intake" Web Form, built and owned
    # directly in Frappe Desk (not part of this app) - these fire on every
    # submission/edit to sync the answers onto the linked Client Lead. See
    # dashboard.api.shared.leads.sync_intake_doctype_submission.
    "Intake Doctype": {
        "after_insert": "dashboard.api.shared.leads.sync_intake_doctype_submission",
        "on_update": "dashboard.api.shared.leads.sync_intake_doctype_submission",
    },
    # Bridges the webshop app's "Contact Us" enquiry (a plain core Lead)
    # into this app's own Client Lead board and notifies Ashley/office -
    # see webshop_lead_sync.py's module docstring for why this needs both
    # hooks rather than just one.
    "Lead": {
        "after_insert": "dashboard.api.shared.webshop_lead_sync.sync_webshop_lead",
    },
    "Comment": {
        "after_insert": "dashboard.api.shared.webshop_lead_sync.sync_webshop_lead_comment",
    },
    # Notifies whoever a document was just allocated to. The requirement
    # itself is created/validated entirely by the user's own "Prepare
    # coach document requirement" Server Script (Before Insert) - this
    # only runs after that succeeds, so it never affects whether the
    # requirement is created.
    "Coach Document Requirement": {
        "after_insert": "dashboard.api.shared.practice_documents.notify_requirement_assigned",
    },
    # Keeps a Practice Document's coach access (and Resource Availability)
    # in sync with its Linked Items, which are managed directly on the
    # document in the Frappe Desk. See
    # item_access.sync_practice_document_resource_access. Deliberately
    # never touches Document Purpose - a Workshop Resource stays Internal
    # Compliance (gated purely by Item Access), not Client Resource.
    "Practice Document": {
        "on_update": [
            "dashboard.api.shared.item_access.sync_practice_document_resource_access",
            # Keeps required_action/mandatory/declaration text/etc on any
            # still-open Coach Document Requirement in sync with the
            # Practice Document, which the Desk's own "Prepare coach
            # document requirement" Server Script only ever copies once,
            # at creation. See practice_documents.sync_requirement_snapshot_fields.
            "dashboard.api.shared.practice_documents.sync_requirement_snapshot_fields",
            # Ticking a Brand Access checkbox grants every coach on that
            # brand a Coach Document Requirement. See
            # practice_documents.sync_practice_document_brand_requirements.
            "dashboard.api.shared.practice_documents.sync_practice_document_brand_requirements",
        ],
    },
    # Other half of brand-based document access - a coach's own Brand
    # Access changing (e.g. becoming a People franchisee) picks up every
    # document already tagged with that brand. See
    # practice_documents.sync_coach_brand_document_requirements. Coach is
    # a core doctype this app doesn't own the JSON for, same as Item.
    "Coach": {
        "on_update": [
            "dashboard.api.shared.practice_documents.sync_coach_brand_document_requirements",
            # Provisions the Coach Onboarding Journey the one time
            # start_onboarding is ticked - see onboarding.provision_onboarding_steps.
            "dashboard.api.shared.onboarding.provision_onboarding_steps",
        ],
    },
    # Session Worker equivalent of the Coach hook above. See
    # practice_documents.sync_session_worker_brand_document_requirements.
    "Session Worker": {
        "on_update": "dashboard.api.shared.practice_documents.sync_session_worker_brand_document_requirements",
    },
    # link_url/lms_course/lms_chapter/lms_lesson_number are "always
    # current" fields (not a point-in-time snapshot like step_name,
    # which stays whatever a coach was actually told at the time), so any
    # edit here needs to reach every coach already on this step - from
    # ANY save path (a direct Desk edit, not just the franchisor Manage
    # Step List screen). See onboarding.sync_master_step_link_fields.
    "Coach Onboarding Master Step": {
        "on_update": [
            "dashboard.api.shared.onboarding.sync_master_step_link_fields",
            # Unticking Active removes this step from every coach's
            # checklist outright, re-ticking adds it back onto everyone
            # already onboarding - see onboarding.sync_master_step_active_state.
            "dashboard.api.shared.onboarding.sync_master_step_active_state",
        ],
        # Deleting the master step outright (not just unticking Active)
        # used to leave every coach's own row for it stranded, silently
        # inflating total_steps forever after - see
        # onboarding.remove_coach_steps_on_master_step_delete.
        "on_trash": "dashboard.api.shared.onboarding.remove_coach_steps_on_master_step_delete",
    },
    # Frappe Learning is a separate app - this doesn't touch its own
    # controller, Frappe runs every registered app's hooks for a
    # doctype alongside its own. See lms_certificates.py.
    "LMS Certificate": {
        "validate": "dashboard.api.shared.lms_certificates.block_certificate_before_course_complete",
    },
    # "Show In Dashboard Reports" / "Also Show To Coaches" on the Web Form
    # itself (custom fields, see the add_web_form_report_visibility_fields
    # patch) drive Reports-section visibility automatically - see
    # form_reports.sync_web_form_report_visibility.
    "Web Form": {
        "on_update": "dashboard.api.shared.form_reports.sync_web_form_report_visibility",
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
            "dashboard.api.shared.booking_confirmations.send_pending_booking_confirmations",
            "dashboard.api.shared.booking_confirmations.send_pending_meet_link_followups",
        ],
    },
    # Keeps every client's age-derived client_type (Kid/Teen/Uni Student/
    # Adult) moving with their real age automatically, even if nobody ever
    # reopens their record - see refresh_all_client_ages_and_types().
    "daily": [
        "dashboard.api.shared.client_details.refresh_all_client_ages_and_types",
    ],
}

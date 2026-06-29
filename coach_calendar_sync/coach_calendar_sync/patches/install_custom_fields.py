"""
Creates all Custom Fields required by the coach_calendar_sync app.
Run via: bench run-patch coach_calendar_sync.patches.install_custom_fields
Also called from install.py on first install.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


GOOGLE_CALENDAR_SECTION = [
    {
        "fieldname": "google_calendar_section",
        "fieldtype": "Section Break",
        "label": "Google Calendar",
        "module": "Coach Calendar Sync",
        "collapsible": 1,
    },
    {
        "fieldname": "google_sync_enabled",
        "fieldtype": "Check",
        "label": "Google Sync Enabled",
        "module": "Coach Calendar Sync",
    },
    {
        "fieldname": "google_email",
        "fieldtype": "Data",
        "label": "Google Email",
        "options": "Email",
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.google_sync_enabled",
    },
    {
        "fieldname": "google_calendar_id",
        "fieldtype": "Data",
        "label": "Google Calendar ID",
        "read_only": 1,
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.google_sync_enabled",
        "description": "Populated automatically after connecting.",
    },
    {
        "fieldname": "refresh_token",
        "fieldtype": "Password",
        "label": "Refresh Token",
        "read_only": 1,
        "module": "Coach Calendar Sync",
        "hidden": 1,
    },
    {
        "fieldname": "access_token",
        "fieldtype": "Small Text",
        "label": "Access Token",
        "read_only": 1,
        "module": "Coach Calendar Sync",
        "hidden": 1,
    },
    {
        "fieldname": "token_expiry",
        "fieldtype": "Datetime",
        "label": "Token Expiry",
        "read_only": 1,
        "module": "Coach Calendar Sync",
        "hidden": 1,
    },
    {
        "fieldname": "connected",
        "fieldtype": "Check",
        "label": "Connected",
        "read_only": 1,
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.google_sync_enabled",
    },
    {
        "fieldname": "last_sync",
        "fieldtype": "Datetime",
        "label": "Last Sync",
        "read_only": 1,
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.google_sync_enabled",
    },
    {
        "fieldname": "last_error",
        "fieldtype": "Small Text",
        "label": "Last Error",
        "read_only": 1,
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.last_error",
    },
    {
        "fieldname": "google_calendar_col_break",
        "fieldtype": "Column Break",
        "module": "Coach Calendar Sync",
    },
    {
        "fieldname": "automatically_create_google_meet",
        "fieldtype": "Check",
        "label": "Automatically Create Google Meet",
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.google_sync_enabled",
    },
    {
        "fieldname": "calendar_colour",
        "fieldtype": "Color",
        "label": "Calendar Colour",
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.google_sync_enabled",
    },
    {
        "fieldname": "google_calendar_buttons",
        "fieldtype": "Section Break",
        "label": "Calendar Actions",
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.google_sync_enabled",
    },
    {
        "fieldname": "connect_google_calendar",
        "fieldtype": "Button",
        "label": "Connect Google Calendar",
        "module": "Coach Calendar Sync",
        "depends_on": "eval:!doc.connected",
    },
    {
        "fieldname": "disconnect_google_calendar",
        "fieldtype": "Button",
        "label": "Disconnect Google Calendar",
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.connected",
    },
    {
        "fieldname": "test_connection",
        "fieldtype": "Button",
        "label": "Test Connection",
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.connected",
    },
]

EVENT_SYNC_FIELDS = [
    {
        "fieldname": "google_sync_section",
        "fieldtype": "Section Break",
        "label": "Google Calendar Sync",
        "module": "Coach Calendar Sync",
        "collapsible": 1,
        "insert_after": "description",
    },
    {
        "fieldname": "custom_sync_status",
        "fieldtype": "Select",
        "label": "Sync Status",
        "options": "\nPending\nSynced\nFailed",
        "default": "",
        "read_only": 1,
        "in_list_view": 0,
        "module": "Coach Calendar Sync",
    },
    {
        "fieldname": "custom_google_event_id",
        "fieldtype": "Data",
        "label": "Google Event ID",
        "read_only": 1,
        "module": "Coach Calendar Sync",
    },
    {
        "fieldname": "custom_google_meet_url",
        "fieldtype": "Data",
        "label": "Google Meet URL",
        "read_only": 1,
        "options": "URL",
        "module": "Coach Calendar Sync",
    },
    {
        "fieldname": "custom_last_sync_error",
        "fieldtype": "Small Text",
        "label": "Last Sync Error",
        "read_only": 1,
        "module": "Coach Calendar Sync",
        "depends_on": "eval:doc.custom_last_sync_error",
    },
]


def execute():
    # Add Google Calendar section to Coach and Session Worker
    fields_by_doctype = {
        "Coach": [dict(f) for f in GOOGLE_CALENDAR_SECTION],
        "Session Worker": [dict(f) for f in GOOGLE_CALENDAR_SECTION],
        "Event": EVENT_SYNC_FIELDS,
    }
    create_custom_fields(fields_by_doctype, ignore_validate=True)
    frappe.db.commit()

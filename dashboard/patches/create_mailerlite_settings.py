"""
Creates "MailerLite Settings" as a Single doctype - where the API key,
target MailerLite Group ID, and the webhook signing secret all live.
Every Frappe Email Group is synced into that one MailerLite Group ID -
see dashboard/api/shared/mailerlite_sync.py for what actually uses
these (and mailerlite_sync_all_email_groups.py, which drops the
earlier single-group-only field on sites where this patch already
ran).

Runs automatically on the next `bench migrate` - no manual step needed,
but the fields themselves are blank until office fills them in via
Desk (System Manager only).
"""

import frappe

DOCTYPE_NAME = "MailerLite Settings"


def execute():
    if frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": DOCTYPE_NAME,
        "module": "Dashboard",
        "custom": 1,
        "issingle": 1,
        "fields": [
            {
                "fieldname": "api_key",
                "fieldtype": "Password",
                "label": "MailerLite API Key",
                "description": "MailerLite dashboard - Integrations - MailerLite API - API - Use.",
            },
            {
                "fieldname": "group_id",
                "fieldtype": "Data",
                "label": "MailerLite Group ID",
                "description": "The MailerLite group new subscribers from Frappe are added to.",
            },
            {
                "fieldname": "webhook_section",
                "fieldtype": "Section Break",
                "label": "Webhook (MailerLite unsubscribe -> Frappe)",
            },
            {
                "fieldname": "webhook_signing_secret",
                "fieldtype": "Password",
                "label": "Webhook Signing Secret",
                "description": (
                    "Shown by MailerLite when you create the webhook. Register "
                    "https://theresilienthub.co.uk/api/method/dashboard.api.shared.mailerlite_sync."
                    "mailerlite_webhook under MailerLite's Integrations > Webhooks, subscribed to "
                    "the subscriber-unsubscribed event."
                ),
            },
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
    })
    doc.insert(ignore_permissions=True)

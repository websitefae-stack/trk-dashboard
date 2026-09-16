"""
Shared helper for adding someone straight into a marketing Email Group
(core Frappe doctype - Setup > Email > Email Group) when they complete
a guest-facing form. Used by webshop_purchase.py for online orders.

This is intentionally a near-duplicate of resilient_domains.api.website.
email_groups.add_to_email_group() rather than a shared import - this app
never imports resilient_domains' Python code (and vice versa), only
reuses core Frappe doctypes both apps already share on the same site,
same boundary as everywhere else in this codebase.

Deliberately never lets a missing group or an unexpected error here
block the actual form submission/order it's piggybacking on.
"""

import frappe


def add_to_email_group(email, group_name, full_name=None):
    email = (email or "").strip().lower()

    if not email or not group_name:
        return

    try:
        if not frappe.db.exists("Email Group", group_name):
            return

        existing = frappe.db.get_value(
            "Email Group Member", {"email_group": group_name, "email": email}, "name"
        )

        if existing:
            frappe.db.set_value("Email Group Member", existing, "unsubscribed", 0)
            return

        member = frappe.new_doc("Email Group Member")
        member.email_group = group_name
        member.email = email

        if full_name and member.meta.has_field("full_name"):
            member.full_name = full_name

        member.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"add_to_email_group failed - {group_name}")

"""
Shared helper for adding someone straight into a marketing Email Group
(core Frappe doctype - Setup > Email > Email Group) when they complete
a guest-facing form. Used by webshop_purchase.py for online orders, and
by course_unlock_on_payment.py's add_paid_enrollment_to_course_email_
group (every LMS Enrollment, however it was created) for the per-course
group below.

This is intentionally a near-duplicate of resilient_domains.api.website.
email_groups.add_to_email_group()/ensure_email_group() rather than a
shared import - this app never imports resilient_domains' Python code
(and vice versa), only reuses core Frappe doctypes both apps already
share on the same site, same boundary as everywhere else in this
codebase.

Deliberately never lets a missing group or an unexpected error here
block the actual form submission/order it's piggybacking on.
"""

import frappe


def course_signup_email_group_name(course_title):
    """
    Must match resilient_domains.api.course_signup._course_signup_email_
    group() exactly, name for name - a course bought through the store
    (this app) and a course joined through the free direct-signup form
    (resilient_domains) need to land the SAME people in the SAME group,
    not two separate ones for the same course.
    """
    title = (course_title or "").strip()
    return f"{title} Sign-ups" if title else None


def ensure_email_group(group_name):
    if not group_name:
        return

    try:
        if frappe.db.exists("Email Group", group_name):
            return

        title_field = "title" if frappe.get_meta("Email Group").has_field("title") else None

        doc = frappe.new_doc("Email Group")

        if title_field:
            doc.set(title_field, group_name)
        else:
            doc.name = group_name

        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"ensure_email_group failed - {group_name}")


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

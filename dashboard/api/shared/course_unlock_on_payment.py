"""
Auto-unlocks a linked LMS course, and grants client_portal login access
if the buyer doesn't already have it, the moment an invoice containing a
course-unlocking item (Item.custom_unlocks_lms_course - see
store_products.py, already used by webshop_purchase.py's guest-checkout
equivalent) is actually PAID, not merely invoiced/submitted. Deliberately
hooked on Payment Entry.on_submit rather than Sales Invoice.on_submit - a
session pack is invoiced long before it's paid, and the free course
access is meant as a reward for payment, not for just being billed.

Data-driven, not tied to any specific pack: whichever Item(s) get
custom_unlocks_lms_course set (via the Store product editor, or directly
in Desk for a non-store item) trigger this - e.g. only the 12 Session
Coaching Pack, never the 4 Session Coaching Pack, purely because that's
the only one with the field set. No item codes are hardcoded here.

This covers the general (non-webshop) invoice flow - a coach/office
member raises an invoice, the client pays by bank transfer, then
office marks it paid via dashboard.py/invoices.py, both of which funnel
through payment_utils.build_and_submit_payment_entry(), which always
ends in a real, submitted Payment Entry. A Payment Entry created
directly in Desk is covered the same way, since this hooks the core
doctype event rather than either app helper.

Every failure here is caught and logged rather than raised, since this
fires inside Payment Entry.on_submit itself - this must never block a
real payment from recording.
"""

import frappe

from dashboard.api.shared import payment_utils
from dashboard.api.shared.invoices import _client_display_name
from dashboard.api.shared.permissions import ensure_office_user


def unlock_courses_on_payment(doc, method=None):
    try:
        _unlock_courses_on_payment(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Course Unlock On Payment Failed - {doc.name}")


@frappe.whitelist()
def backfill_course_unlocks_for_paid_invoices():
    """Franchisor-triggerable, safe to re-run any time - e.g. right after
    setting custom_unlocks_lms_course on an item for the first time, to
    retroactively grant access on every already-paid invoice that
    contains it (not just ones paid from now on). Every invoice it
    touches goes through the exact same _process_invoice() the live
    Payment Entry hook uses, so anyone already enrolled is simply
    skipped again - no duplicate enrolment, no repeat "you now have
    access" email.
    """
    ensure_office_user()
    return _backfill_course_unlocks_for_paid_invoices()


def _backfill_course_unlocks_for_paid_invoices():
    if not frappe.db.exists("DocType", "LMS Course"):
        return {"invoices_checked": 0}

    if not frappe.get_meta("Item").has_field("custom_unlocks_lms_course"):
        return {"invoices_checked": 0}

    item_codes = frappe.get_all(
        "Item",
        filters={"custom_unlocks_lms_course": ["not in", ["", None]]},
        pluck="name",
    )

    if not item_codes:
        return {"invoices_checked": 0}

    invoice_names = set(
        frappe.get_all(
            "Sales Invoice Item",
            filters={"item_code": ["in", item_codes], "parenttype": "Sales Invoice"},
            pluck="parent",
        )
    )

    for invoice_name in invoice_names:
        try:
            _process_invoice(invoice_name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Backfill Course Unlock Failed - {invoice_name}")

    frappe.db.commit()

    return {"invoices_checked": len(invoice_names)}


def _unlock_courses_on_payment(doc):
    if doc.payment_type != "Receive":
        return

    if not frappe.db.exists("DocType", "LMS Course"):
        return

    if not frappe.get_meta("Item").has_field("custom_unlocks_lms_course"):
        return

    for reference in doc.references or []:
        if reference.reference_doctype != "Sales Invoice" or not reference.reference_name:
            continue

        _process_invoice(reference.reference_name)


def _process_invoice(invoice_name):
    if not frappe.db.exists("Sales Invoice", invoice_name):
        return

    invoice = frappe.get_doc("Sales Invoice", invoice_name)

    if invoice.docstatus != 1:
        return

    # A guest webshop order (custom_online_client only ever gets set by
    # webshop_purchase.py's Stripe fulfilment) already runs its own
    # course-unlock + portal-access + order-confirmation-email logic
    # end-to-end, synchronously, as part of creating this very invoice -
    # before this hook ever fires. Re-running it here would be harmless
    # to the enrolment itself (already-enrolled checks are idempotent),
    # but would send a second, redundant "you now have access" email on
    # top of that flow's own order confirmation.
    if invoice.meta.has_field("custom_online_client") and invoice.get("custom_online_client"):
        return

    if not invoice.meta.has_field("custom_client"):
        return

    outstanding = payment_utils.get_outstanding_amount_for_payment(
        invoice.outstanding_amount, invoice.grand_total, invoice.name
    )
    if outstanding > 0.01:
        return

    client_name = invoice.get("custom_client")
    if not client_name or not frappe.db.exists("Client", client_name):
        return

    courses = []
    for row in invoice.items or []:
        if not row.item_code:
            continue
        course = frappe.db.get_value("Item", row.item_code, "custom_unlocks_lms_course")
        if course and course not in courses:
            courses.append(course)

    if not courses:
        return

    email, full_name, contact_name = _resolve_client_contact(client_name)
    if not email:
        frappe.log_error(
            f"Client {client_name} has no email on file - could not grant course access for invoice {invoice_name}",
            "Course Unlock On Payment - No Email",
        )
        return

    newly_enrolled = _enrol_in_courses(email, courses)
    if not newly_enrolled:
        return

    from dashboard.api.shared.webshop_purchase import _ensure_portal_access
    from dashboard.api.shared.portal_access import _ensure_user_account

    granted_new_portal_access = _ensure_portal_access(client_name, contact_name, email)
    user_created = _ensure_user_account(email, full_name)

    _send_course_access_email(email, full_name, newly_enrolled, user_created or granted_new_portal_access)


def _resolve_client_contact(client_name):
    """Mirrors invoices.py's get_client_email_options priority (Client's
    own email field, then billing contact, then any contact with an
    email on file) without its login-required permission check, since
    this runs from inside a system hook.
    """
    client_doc = frappe.get_doc("Client", client_name)
    client_rows = client_doc.get("client_contacts") or []
    billing_contact = client_doc.get("billing_contact")

    email = (client_doc.get("email") or "").strip() if client_doc.meta.has_field("email") else ""
    contact_name = None

    if email:
        for row in client_rows:
            if (row.get("email_id") or "").strip().lower() == email.lower():
                contact_name = row.get("contact")
                break
    else:
        for row in client_rows:
            if billing_contact and row.get("contact") == billing_contact and row.get("email_id"):
                email = row.get("email_id")
                contact_name = row.get("contact")
                break

        if not email:
            for row in client_rows:
                if row.get("email_id"):
                    email = row.get("email_id")
                    contact_name = row.get("contact")
                    break

    full_name = _client_display_name(client_name)

    return (email or "").strip(), full_name, contact_name


def _enrol_in_courses(email, courses):
    newly_enrolled = []

    for course in courses:
        if not frappe.db.exists("LMS Course", course):
            continue

        if frappe.db.exists("LMS Enrollment", {"course": course, "member": email}):
            continue

        enrollment = frappe.new_doc("LMS Enrollment")
        enrollment.course = course
        enrollment.member = email
        enrollment.insert(ignore_permissions=True)
        newly_enrolled.append(course)

    return newly_enrolled


def _send_course_access_email(email, full_name, courses, mention_login_details):
    course_titles = [
        frappe.db.get_value("LMS Course", course, "title") or course for course in courses
    ]
    courses_line = ", ".join(course_titles)

    login_url = frappe.utils.get_url("/login")
    greeting = f"Hi {full_name}," if full_name else "Hi,"

    message = f"""
        <p>{greeting}</p>
        <p>Thanks for your payment - you now have free access to: <strong>{courses_line}</strong>.</p>
    """

    if mention_login_details:
        message += f"""
            <p><a href="{login_url}">Log in to the client portal here</a> to get started.</p>
            <p>Your username is your email address: <strong>{email}</strong></p>
            <p>Your temporary password is your email address (the same as above). You can change this any time using "Forgot Password" on the login page.</p>
        """
    else:
        message += f"""
            <p><a href="{login_url}">Log in to the client portal here</a> to get started - use your existing login details.</p>
        """

    frappe.sendmail(
        recipients=[email],
        subject=f"You now have access to {course_titles[0]}" if len(course_titles) == 1 else "You now have access to your new course",
        message=message,
        now=True,
    )

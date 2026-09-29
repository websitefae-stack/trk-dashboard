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
from frappe.utils import getdate

from dashboard.api.shared import payment_utils
from dashboard.api.shared.invoices import _client_display_name
from dashboard.api.shared.permissions import ensure_office_user

# Ashley's explicit cutoff before this feature went live: only invoices
# dated on or after this should ever grant course access - an older
# invoice must never retroactively unlock the course, even if it's paid
# (or gets caught by the backfill) after this date.
COURSE_UNLOCK_CUTOFF_DATE = "2026-03-01"


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

    if invoice.posting_date and getdate(invoice.posting_date) < getdate(COURSE_UNLOCK_CUTOFF_DATE):
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

    _ensure_portal_access(client_name, contact_name, email)
    _ensure_user_account(email, full_name)

    _send_course_access_email(email, full_name, newly_enrolled)


def _resolve_client_contact(client_name):
    """The course is linked to the Client, but access only ever goes to
    whoever is actually paying the bill - the Client's own
    billing_contact - never any other contact linked to the Client (a
    second parent/guardian, emergency contact, etc, even if they happen
    to have an email on file). Falls back to the Client's own email only
    when there's no billing_contact set at all, since a self-paying
    adult client is their own payer with no separate contact record.
    """
    client_doc = frappe.get_doc("Client", client_name)
    billing_contact = client_doc.get("billing_contact")

    email = ""
    contact_name = None

    if billing_contact:
        for row in client_doc.get("client_contacts") or []:
            if row.get("contact") == billing_contact and row.get("email_id"):
                email = row.get("email_id")
                contact_name = row.get("contact")
                break

        if not email:
            billing_email = frappe.db.get_value("Contact", billing_contact, "email_id")
            if billing_email:
                email = billing_email
                contact_name = billing_contact

    if not email and client_doc.meta.has_field("email"):
        email = (client_doc.get("email") or "").strip()

    full_name = _client_display_name(client_name)

    return (email or "").strip(), full_name, contact_name


def _enrol_in_courses(email, courses):
    newly_enrolled = []

    # This function's own caller already sends a tailored "you now have
    # access" email with proper login-details wording right after this
    # returns - skip_lms_enrollment_welcome_email tells the blanket
    # LMS Enrollment.after_insert hook (see send_new_enrollment_welcome_
    # email below) not to also fire its own, more generic one for these
    # inserts specifically.
    frappe.flags.skip_lms_enrollment_welcome_email = True
    try:
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
    finally:
        frappe.flags.skip_lms_enrollment_welcome_email = False

    return newly_enrolled


# The same four brand wordmarks the standalone Web Forms show in their
# own CUSTOM_CSS (e.g. create_twilight_meeting_form.py) - those use CSS
# background-image on a relative /files/ URL, which doesn't work in an
# email (no stylesheet, and relative URLs don't resolve for a reader's
# mail client), so this embeds the same four logos as absolute-URL <img>
# tags instead.
EMAIL_BRAND_LOGO_PATHS = [
    "/files/TRKid_Wordmark_Logo.png",
    "/files/TRTeen_Wordmark_Logo.png",
    "/files/TRPeople_Wordmark_Logo.png",
    "/files/TRSchool_Wordmark_Logo.png",
]


def _email_brand_logo_row():
    # width/height set as real HTML attributes, not just inline CSS -
    # Outlook (and several other mail clients) ignore CSS sizing on
    # <img> entirely and fall back to the image's native pixel size,
    # which is how these ended up rendering huge - the attributes are
    # what those clients actually honour.
    logos = "".join(
        f'<img src="{frappe.utils.get_url(path)}" alt="" width="50" height="50" '
        f'style="width:50px; height:50px; object-fit:contain; margin:0 6px; border:0;">'
        for path in EMAIL_BRAND_LOGO_PATHS
    )
    return f'<div style="margin-top:28px; text-align:center;">{logos}</div>'


def _send_course_access_email(email, full_name, courses):
    course_titles = [
        frappe.db.get_value("LMS Course", course, "title") or course for course in courses
    ]
    courses_line = ", ".join(course_titles)

    login_url = frappe.utils.get_url("/login")
    greeting = f"Hi {full_name}," if full_name else "Hi,"

    message = f"""
        <p>{greeting}</p>
        <p>Thank you for signing up for <strong>{courses_line}</strong>.</p>
        <p>You can log in by <a href="{login_url}">clicking here</a>. If this is the first time logging in,
        please set your password by clicking "Forgot Password".</p>
        <p>If you have any questions or issues, please reach out to
        <a href="mailto:office@theresilienthub.co.uk">office@theresilienthub.co.uk</a>.</p>
        <p>Kind regards,<br>
        Chantelle Venter<br>
        Business Manager<br>
        The Resilient Hub</p>
        {_email_brand_logo_row()}
    """

    frappe.sendmail(
        recipients=[email],
        subject=f"You now have access to {course_titles[0]}" if len(course_titles) == 1 else "You now have access to your new course",
        message=message,
        now=True,
    )


def send_new_enrollment_welcome_email(doc, method=None):
    """LMS Enrollment.after_insert hook - catches every enrollment that
    ISN'T already handled by one of this app's own flows (the payment
    unlock above, webshop_purchase.py's checkout unlock, or
    resilient_domains' self-service course signup - each of those sets
    skip_lms_enrollment_welcome_email around its own insert() and sends
    its own, more specific email straight after). Chiefly this is a
    coach or office member adding someone to a course by hand - in Desk,
    or via Frappe LMS's own "Add student"/enrol UI - neither of which
    ever emails the person anything on their own, which is the actual
    "no thank-you/login-details email" gap this closes.

    Every failure is caught and logged, never raised - this must never
    block an enrollment from saving.
    """
    if frappe.flags.get("skip_lms_enrollment_welcome_email"):
        return

    try:
        _send_new_enrollment_welcome_email(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"LMS Enrollment Welcome Email Failed - {doc.name}")


def _send_new_enrollment_welcome_email(doc):
    email = (doc.member or "").strip()
    if not email or "@" not in email:
        return

    if not frappe.db.exists("LMS Course", doc.course):
        return

    full_name = (
        frappe.db.get_value("User", email, "full_name")
        or frappe.db.get_value("Contact", {"email_id": email}, "full_name")
        or ""
    )

    from dashboard.api.shared.portal_access import _ensure_user_account

    user_created = _ensure_user_account(email, full_name)

    _send_course_access_email(email, full_name, [doc.course])


@frappe.whitelist()
def send_welcome_emails_to_existing_course_members(dry_run=1, only_email=None):
    """One-off, office-triggered backfill - everyone already enrolled in
    an LMS course from before send_new_enrollment_welcome_email existed
    never got a welcome/login-details email at all. One email per
    person (not per enrollment) listing every course they already have
    access to.

    Call with no arguments (or ?dry_run=1) first - it sends nothing,
    just returns who WOULD be emailed and what courses they'd be told
    about, so the list can be checked before anything actually goes
    out. Call again with ?dry_run=0 to actually send.

    only_email restricts an actual send (dry_run=0) to just that one
    address - e.g. ?dry_run=0&only_email=you@example.com to see the real
    email land in one inbox first, before running it for everyone.
    Ignored on a dry run (which already lists everyone regardless).
    """
    ensure_office_user()

    dry_run = str(dry_run).strip().lower() not in ("0", "false", "no")
    only_email = (only_email or "").strip().lower()

    enrollments = frappe.get_all("LMS Enrollment", fields=["member", "course"])

    courses_by_member = {}
    for row in enrollments:
        member = (row.member or "").strip()
        if not member or "@" not in member:
            continue
        courses_by_member.setdefault(member, []).append(row.course)

    people = []
    emails_sent = 0
    # only_email is easy to mistype or to give as an address that isn't
    # actually the one enrolled under (e.g. a personal inbox rather than
    # the login email on the enrollment) - surfaced explicitly below
    # rather than just quietly sending nothing, since that's exactly what
    # a silent no-match and a silent failure both look like otherwise.
    only_email_matched = False
    only_email_error = None

    for member, courses in courses_by_member.items():
        full_name = (
            frappe.db.get_value("User", member, "full_name")
            or frappe.db.get_value("Contact", {"email_id": member}, "full_name")
            or ""
        )
        course_titles = [frappe.db.get_value("LMS Course", c, "title") or c for c in courses]
        people.append({"email": member, "full_name": full_name, "courses": course_titles})

        is_only_email_target = bool(only_email) and member.strip().lower() == only_email
        if is_only_email_target:
            only_email_matched = True

        if not dry_run and (not only_email or is_only_email_target):
            try:
                from dashboard.api.shared.portal_access import _ensure_user_account

                _ensure_user_account(member, full_name)
                _send_course_access_email(member, full_name, courses)
                emails_sent += 1
            except Exception:
                traceback_str = frappe.get_traceback()
                frappe.log_error(traceback_str, f"Backfill Course Welcome Email Failed - {member}")
                if is_only_email_target:
                    only_email_error = traceback_str

    return {
        "dry_run": dry_run,
        "only_email": only_email or None,
        "only_email_matched": only_email_matched if only_email else None,
        "only_email_error": only_email_error,
        "total_people": len(people),
        "emails_actually_sent": emails_sent,
        "people": people,
    }

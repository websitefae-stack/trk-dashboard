import frappe
from frappe import _


COACH_DOCTYPE = "Coach"
CHANGE_REQUEST_DOCTYPE = "Change Request"

OFFICE_EMAIL = "office@theresilientpeople.co.uk"
ASHLEY_USER = "ashley@theresilientkid.co.uk"


def ensure_logged_in():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def get_coach_doc():
    ensure_logged_in()

    coach_name = frappe.db.get_value(
        COACH_DOCTYPE,
        {"user": frappe.session.user},
        "name",
    )

    if not coach_name:
        coach_name = frappe.db.get_value(
            COACH_DOCTYPE,
            {"coach_email": frappe.session.user},
            "name",
        )

    if not coach_name:
        frappe.throw(_("No Coach profile linked."), frappe.PermissionError)

    return frappe.get_doc(COACH_DOCTYPE, coach_name)


def get_coach_display_name():
    doc = get_coach_doc()
    return doc.coach_name or doc.name


@frappe.whitelist()
def update_my_coach_profile():
    ensure_logged_in()

    coach = get_coach_doc()

    coach.bio = frappe.form_dict.get("bio")

    if frappe.request.files.get("photo"):
        file = frappe.request.files.get("photo")

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file.filename,
            "attached_to_doctype": COACH_DOCTYPE,
            "attached_to_name": coach.name,
            "content": file.stream.read(),
            "is_private": 1,
        })
        file_doc.save(ignore_permissions=True)

        coach.photo = file_doc.file_url

    coach.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "message": "Profile updated."}


@frappe.whitelist()
def request_my_banking_change(new_banking_details=None, banking_change_reason=None):
    ensure_logged_in()

    coach = get_coach_doc()

    if not new_banking_details:
        frappe.throw(_("Enter new banking details."))

    doc = frappe.new_doc(CHANGE_REQUEST_DOCTYPE)

    doc.banking_change_for = "Coach"
    doc.banking_coach = coach.name
    doc.new_banking_details = new_banking_details
    doc.banking_change_reason = banking_change_reason
    doc.banking_change_status = "New"
    doc.change_requested_by = frappe.session.user
    doc.request_date = frappe.utils.now_datetime()

    doc.insert(ignore_permissions=True)

    # EMAIL OFFICE
    frappe.sendmail(
        recipients=[OFFICE_EMAIL],
        subject="Coach Banking Change Request",
        message=f"{coach.coach_name} submitted a banking change request.",
    )

    # NOTIFY ASHLEY
    frappe.get_doc({
        "doctype": "TRK Notification",
        "recipient_user": ASHLEY_USER,
        "notification_type": "Coach Banking Change",
        "message": f"{coach.coach_name} submitted a banking change request.",
        "status": "Unread",
        "notification_date": frappe.utils.now_datetime(),
    }).insert(ignore_permissions=True)

    frappe.db.commit()

    return {"ok": 1, "message": "Request submitted."}

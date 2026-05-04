import frappe
from frappe import _
from werkzeug.utils import secure_filename

from dashboard.api.shared.notifications import create_trk_notification


COACH_DOCTYPE = "Coach"
CHANGE_REQUEST_DOCTYPE = "Change Request"

OFFICE_EMAIL = "office@theresilientpeople.uk"
ASHLEY_USER = "ashley@theresilientkid.co.uk"

LEGAL_TABLE_CONFIG = {
    "dbs": {
        "parentfield": "dbs",
        "label": "DBS",
        "number_field": "dbs_number",
        "file_field": "dbs_file",
    },
    "dbs_update_service": {
        "parentfield": "dbs_update_services",
        "label": "DBS Update Service",
        "number_field": "dbs_number",
        "file_field": "update_service_file",
    },
    "insurance": {
        "parentfield": "insurance",
        "label": "Insurance",
        "number_field": "insurance_number",
        "file_field": "insurance_file",
        "insurer_field": "insurer_name",
    },
    "indemnity": {
        "parentfield": "indemnity",
        "label": "Indemnity",
        "number_field": "indemnity_number",
        "file_field": "indemnity_file",
        "insurer_field": "insurer_name",
    },
}


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

    if coach.meta.has_field("bio"):
        coach.bio = frappe.form_dict.get("bio")

    if coach.meta.has_field("interest"):
        coach.interest = frappe.form_dict.get("interest")

    photo_url = _save_optional_file("photo", coach)

    if photo_url and coach.meta.has_field("photo"):
        coach.photo = photo_url

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

    frappe.sendmail(
        recipients=[OFFICE_EMAIL],
        subject="Coach Banking Change Request",
        message=f"{coach.coach_name or coach.name} submitted a banking change request.",
    )

    create_trk_notification(
        recipient_user=ASHLEY_USER,
        notification_type="Coach Banking Change",
        message=f"{coach.coach_name or coach.name} submitted a banking change request.",
        priority="High",
        reference_doctype=CHANGE_REQUEST_DOCTYPE,
        reference_name=doc.name,
        coach=coach.name,
    )

    frappe.db.commit()

    return {"ok": 1, "message": "Request submitted."}


@frappe.whitelist()
def add_my_legal_record():
    ensure_logged_in()

    coach = get_coach_doc()

    record_type = (frappe.form_dict.get("record_type") or "").strip()
    config = LEGAL_TABLE_CONFIG.get(record_type)

    if not config:
        frappe.throw(_("Invalid legal record type."))

    parentfield = config["parentfield"]

    if not coach.meta.has_field(parentfield):
        frappe.throw(_("Coach is missing field: {0}").format(parentfield))

    file_url = _save_optional_file(config["file_field"], coach)

    if not file_url:
        frappe.throw(_("Please attach the required file."))

    child = coach.append(parentfield, {})

    child.status = _get_status_from_expiry(frappe.form_dict.get("expiry_date"))
    child.date_received = frappe.form_dict.get("date_received")
    child.expiry_date = frappe.form_dict.get("expiry_date")

    child.set(config["number_field"], frappe.form_dict.get("number"))

    if config.get("insurer_field"):
        child.set(config["insurer_field"], frappe.form_dict.get("insurer_name"))

    child.set(config["file_field"], file_url)

    coach.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "message": "{0} added successfully.".format(config["label"]),
    }


def _get_status_from_expiry(expiry_date):
    if not expiry_date:
        return "Expired"

    try:
        expiry = frappe.utils.getdate(expiry_date)
        today = frappe.utils.getdate(frappe.utils.today())
        return "Current" if expiry >= today else "Expired"
    except Exception:
        return "Expired"


def _save_optional_file(fieldname, coach):
    if not getattr(frappe, "request", None):
        return ""

    uploaded_file = frappe.request.files.get(fieldname)

    if not uploaded_file:
        return ""

    filename = secure_filename(uploaded_file.filename or "uploaded-file")

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "attached_to_doctype": COACH_DOCTYPE,
        "attached_to_name": coach.name,
        "content": uploaded_file.stream.read(),
        "is_private": 1,
    })

    file_doc.save(ignore_permissions=True)

    return file_doc.file_url

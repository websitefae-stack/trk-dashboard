import frappe
from frappe import _
from werkzeug.utils import secure_filename

from dashboard.api.shared.notifications import create_trk_notification


SESSION_WORKER_DOCTYPE = "Session Worker"
CHANGE_REQUEST_DOCTYPE = "Change Request"

OFFICE_USER = "office@theresilientpeople.uk"


LEGAL_TABLE_CONFIG = {
    "dbs": {
        "parentfield": "dbs",
        "label": "DBS",
        "number_field": "dbs_number",
        "file_field": "dbs_file",
    },
    "dbs_update_service": {
        "parentfield": "dbs_update_service",
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


def get_session_worker_doc():
    ensure_logged_in()

    session_worker_name = frappe.db.get_value(
        SESSION_WORKER_DOCTYPE,
        {
            "user": frappe.session.user,
        },
        "name",
    )

    if not session_worker_name:
        session_worker_name = frappe.db.get_value(
            SESSION_WORKER_DOCTYPE,
            {
                "sw_email": frappe.session.user,
            },
            "name",
        )

    if not session_worker_name:
        frappe.throw(_("No Session Worker profile is linked to your user."), frappe.PermissionError)

    return frappe.get_doc(SESSION_WORKER_DOCTYPE, session_worker_name)


def get_session_worker_display_name():
    session_worker = get_session_worker_doc()
    return session_worker.sw_name or session_worker.name


@frappe.whitelist()
def update_my_session_worker_profile():
    ensure_logged_in()

    session_worker = get_session_worker_doc()

    editable_fields = [
        "first_name",
        "middle_name",
        "last_name",
        "phone",
        "gender",
        "location",
        "bio",
        "interest",
    ]

    for fieldname in editable_fields:
        if session_worker.meta.has_field(fieldname):
            session_worker.set(fieldname, frappe.form_dict.get(fieldname))

    photo_url = _save_optional_file("photo", session_worker)

    if photo_url:
        session_worker.photo = photo_url

    session_worker.save(ignore_permissions=True)

    if session_worker.get("user"):
        user_updates = {}

        if session_worker.meta.has_field("phone"):
            user_updates["phone"] = session_worker.phone

        if session_worker.meta.has_field("location"):
            user_updates["location"] = session_worker.location

        if session_worker.meta.has_field("bio"):
            user_updates["bio"] = session_worker.bio

        if photo_url:
            user_updates["user_image"] = photo_url

        if user_updates:
            frappe.db.set_value("User", session_worker.get("user"), user_updates)

    frappe.db.commit()

    return {
        "ok": 1,
        "message": "Profile updated successfully.",
    }


@frappe.whitelist()
def request_my_banking_change(new_banking_details=None, banking_change_reason=None):
    ensure_logged_in()

    if not frappe.db.exists("DocType", CHANGE_REQUEST_DOCTYPE):
        frappe.throw(_("Change Request DocType does not exist."))

    session_worker = get_session_worker_doc()

    new_banking_details = (new_banking_details or "").strip()
    banking_change_reason = (banking_change_reason or "").strip()

    if not new_banking_details:
        frappe.throw(_("Please enter the new banking details."))

    doc = frappe.new_doc(CHANGE_REQUEST_DOCTYPE)
    meta = frappe.get_meta(CHANGE_REQUEST_DOCTYPE)

    values = {
        "banking_change_for": "Session Worker",
        "banking_session_worker": session_worker.name,
        "new_banking_details": new_banking_details,
        "banking_change_reason": banking_change_reason,
        "banking_change_status": "New",
        "change_requested_by": frappe.session.user,
        "request_date": frappe.utils.now_datetime(),
    }

    for fieldname, value in values.items():
        if meta.has_field(fieldname):
            doc.set(fieldname, value)

    doc.insert(ignore_permissions=True)

    create_trk_notification(
        recipient_user=OFFICE_USER,
        notification_type="Session Worker Banking Change Request",
        message="{0} submitted a banking change request.".format(
            session_worker.sw_name or session_worker.name
        ),
        priority="High",
        reference_doctype=CHANGE_REQUEST_DOCTYPE,
        reference_name=doc.name,
        session_worker=session_worker.name,
    )

    frappe.db.commit()

    return {
        "ok": 1,
        "name": doc.name,
        "message": _("Banking change request submitted successfully."),
    }


@frappe.whitelist()
def add_my_legal_record():
    ensure_logged_in()

    session_worker = get_session_worker_doc()

    record_type = (frappe.form_dict.get("record_type") or "").strip()
    config = LEGAL_TABLE_CONFIG.get(record_type)

    if not config:
        frappe.throw(_("Invalid legal record type."))

    parentfield = config["parentfield"]

    if not session_worker.meta.has_field(parentfield):
        frappe.throw(_("Session Worker is missing field: {0}").format(parentfield))

    file_url = _save_optional_file(config["file_field"], session_worker)

    if not file_url:
        frappe.throw(_("Please attach the required file."))

    child = session_worker.append(parentfield, {})

    child.status = _get_status_from_expiry(frappe.form_dict.get("expiry_date"))
    child.date_received = frappe.form_dict.get("date_received")
    child.expiry_date = frappe.form_dict.get("expiry_date")

    child.set(config["number_field"], frappe.form_dict.get("number"))

    if config.get("insurer_field"):
        child.set(config["insurer_field"], frappe.form_dict.get("insurer_name"))

    child.set(config["file_field"], file_url)

    session_worker.save(ignore_permissions=True)
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


def _save_optional_file(fieldname, session_worker):
    if not getattr(frappe, "request", None):
        return ""

    uploaded_file = frappe.request.files.get(fieldname)

    if not uploaded_file:
        return ""

    filename = secure_filename(uploaded_file.filename or "uploaded-file")

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "attached_to_doctype": SESSION_WORKER_DOCTYPE,
        "attached_to_name": session_worker.name,
        "content": uploaded_file.stream.read(),
        "is_private": 1,
    })

    file_doc.save(ignore_permissions=True)

    return file_doc.file_url

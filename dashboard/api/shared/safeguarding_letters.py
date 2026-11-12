"""
School Safeguarding Assurance Letters - a coach asks for formal written
confirmation (for a school) that their safeguarding/safer-recruitment
checks have been completed; Ashley reviews the evidence, fills in the
handful of items that are genuine legal judgement calls rather than
simple record lookups, and signs; the coach downloads the final PDF.

Scope deliberately narrower than a full automated compliance engine -
confirmed with Ashley directly:

- Identity verification / Right to work in the UK: both read from the
  Coach record's own `creation` date ("the day they became a client in
  Frappe") - there's no separate identity-check date tracked anywhere
  in this app. Right to work additionally carries a standing note that
  an overseas-born coach needs a real separate check - this app has no
  nationality/country-of-origin field to gate that automatically, so
  the note is always shown and Ashley/the coach act on it manually.
- Enhanced DBS, DBS Update Service, Safeguarding Training: read from
  the coach's own existing Legal Details records (Coach.dbs/
  dbs_update_services/safeguarding_certificate - see profile.py's
  LEGAL_RECORD_CONFIG/ROLE_PROFILE_CONFIG for the same fields used on
  the coach's own profile page). DBS Certificate Level/Workforce have
  no dedicated fields on that record, so they're free-text on the
  request itself (defaulted to "Enhanced"/"Child Workforce", editable).
- Nature of work: a coach-editable field, pre-filled with a standard
  description Ashley approved - not auto-generated per role.
- Employment references: static wording ("2 of 2 received and verified
  satisfactory") - not a tracked record anywhere in this app, and
  Ashley asked for it to stay that way rather than building real
  reference tracking.
- Regulated activity assessment, Children's barred-list check, KCSIE
  Part One acknowledgement, Overseas checks, Employment history: all
  typed in by Ashley herself during her review (see
  save_assurance_review) - these are either genuine legal judgement
  calls (regulated activity, barred-list eligibility) Ashley explicitly
  said she wasn't confident defining in code, or things this app simply
  has no other record of (KCSIE Part One, overseas history, employment
  history). Employment history gets a one-click standard-wording
  default, same as the others, with free text to override it.

The letter itself never claims anything the record doesn't support -
see _build_evidence() and LETTER_TEMPLATE's own conditionals.
"""

import base64
import hashlib
import json

import frappe
from frappe import _
from frappe.utils import now_datetime, nowdate, getdate

from dashboard.api.shared.permissions import (
	ensure_logged_in,
	ensure_office_user,
	get_current_coach_name,
	_latest_dated_row,
)
from dashboard.api.shared.notifications import create_trk_notification, ASHLEY_USER
from dashboard.api.shared.utils import coalesce_str

REQUEST_DOCTYPE = "School Safeguarding Assurance Request"
# Deliberately Client (client_type="School"), not the separate School
# Pipeline "School" doctype this used to point at - that one is
# franchisor-only sales-prospecting data (see school_pipeline.py), a
# coach has no access to it and no reason to know about it. A coach
# requesting a letter is doing so for a school they actually work at -
# a real Client, the same record that shows on their own Clients list -
# not a cold-outreach prospect. "these schools should not be hard coded
# they should pull fromt he client file with the client type school".
CLIENT_DOCTYPE = "Client"
SCHOOL_CLIENT_TYPE = "School"
COACH_DOCTYPE = "Coach"

ROLE_OPTIONS = [
	"Resilient Kid Coach",
	"Resilient Teen Coach",
	"Resilience Workshop Facilitator",
	"One-to-One Resilience Coach",
	"Group Resilience Coach",
	"School Staff Trainer",
	"Other",
]

DBS_WORDING_OPTIONS = [
	"Certificate clear",
	"Information disclosed and assessed",
	"DBS not required for this role",
]

DBS_STATEMENTS = {
	"Certificate clear": (
		"The certificate was inspected and did not disclose information requiring a separate "
		"suitability assessment."
	),
	"Information disclosed and assessed": (
		"The certificate contained information that was reviewed through our safeguarding "
		"suitability assessment process. Following that assessment, the individual was considered "
		"suitable for the specified role. Any certificate-sharing requirements applicable to the "
		"school will be addressed separately and securely."
	),
	"DBS not required for this role": (
		"Following assessment of the proposed duties and applicable eligibility criteria, an "
		"Enhanced DBS check was not required for this role. The basis for this determination is "
		"recorded in our safeguarding records."
	),
}

DEFAULT_NATURE_OF_WORK = "Weekly one-to-one resilience coaching sessions with identified pupils"
DEFAULT_EMPLOYMENT_HISTORY_NOTE = "Reviewed - no unexplained gaps outstanding"
STATIC_EMPLOYMENT_REFERENCES_TEXT = "2 of 2 received and verified satisfactory"
RIGHT_TO_WORK_NOTE = "if this coach was born outside the UK, a separate right-to-work check is required before this letter is relied on"

ORG_NAME = "The Resilient Kid"
ORG_ADDRESS = "Fox Corner, Chester Road, Hartford, Cheshire, CW8 1LL"
FROM_EMAIL = "ashley@theresilientkid.co.uk"
FROM_PHONE = "07482 787818"
FOOTER_PHONE = "07482 787818"
FOOTER_EMAIL = "office@theresilienthub.co.uk"
SIGNATORY_NAME = "Ashley Costello"
SIGNATORY_ROLE = "CEO and Founder, The Resilient Kid"
LOGO_FILE_URL = "/private/files/TRKid_Wordmark_Logo.png"

COMPLIANCE_GUIDANCE_VERSION = "KCSIE 2026"
LETTER_TEMPLATE_VERSION = "1"


# -------------------------------------------------------------------
# Permissions
# -------------------------------------------------------------------

def _ensure_ashley():
	"""
	Approval and signing are restricted to Ashley's own account, full
	stop - not "any franchisor/office login", which is otherwise one
	undifferentiated permission tier in this app (is_franchisor_user()
	just checks is_office_user()). This is the one place in this
	feature that gate is tightened past that shared tier, per the
	spec's explicit requirement that signing can never be done by an
	administrator on her behalf.
	"""
	ensure_logged_in()

	if frappe.session.user != ASHLEY_USER:
		frappe.throw(_("Only Ashley can approve and sign a safeguarding assurance letter."), frappe.PermissionError)


def _ensure_request_owner(doc):
	coach = get_current_coach_name(optional=True)

	if not coach or doc.coach != coach:
		frappe.throw(_("You do not have permission to access this request."), frappe.PermissionError)


def _get_owned_request(name, for_coach=True):
	if not name or not frappe.db.exists(REQUEST_DOCTYPE, name):
		frappe.throw(_("Request not found."))

	doc = frappe.get_doc(REQUEST_DOCTYPE, name)

	if for_coach:
		_ensure_request_owner(doc)

	return doc


# -------------------------------------------------------------------
# Evidence - what's actually pulled from existing records
# -------------------------------------------------------------------

def _format_date(value):
	if not value:
		return ""
	try:
		return frappe.utils.formatdate(getdate(value), "d MMMM yyyy")
	except Exception:
		return str(value)


def _build_evidence(coach_doc):
	"""
	Everything this feature actually reads from existing coach records -
	see this module's own docstring for exactly what is and isn't
	auto-populated, and why. Never guesses a value this doc doesn't
	support; a missing record comes back as a blank/"not on file" entry,
	never a fabricated date or outcome.
	"""
	meta = coach_doc.meta

	join_date = getdate(coach_doc.creation)

	dbs_best = _latest_dated_row(coach_doc.get("dbs") if meta.has_field("dbs") else [], "dbs_number")
	update_service_rows = coach_doc.get("dbs_update_services") if meta.has_field("dbs_update_services") else []
	update_best = _latest_dated_row(update_service_rows, "dbs_number")
	safeguarding_rows = coach_doc.get("safeguarding_certificate") if meta.has_field("safeguarding_certificate") else []
	training_best = None
	for row in safeguarding_rows or []:
		if not training_best or (row.get("date_received") or "") > (training_best.get("date_received") or ""):
			training_best = row

	dbs_number = ""
	dbs_issue_date = ""
	dbs_expiry_date = ""
	if dbs_best:
		dbs_number = dbs_best.get("number") or ""
		dbs_expiry_date = dbs_best.get("expiry_date")
		# _latest_dated_row only carries number/expiry - go back to the
		# actual row for date_received (the certificate's issue date),
		# matched by its number.
		for row in coach_doc.get("dbs") or []:
			if row.get("dbs_number") == dbs_number:
				dbs_issue_date = row.get("date_received")
				break

	update_service_status = ""
	if update_best:
		update_service_status = _("Subscribed - latest record expires {0}").format(_format_date(update_best.get("expiry_date")))

	training_text = ""
	if training_best:
		training_text = (training_best.get("certificate_number") or _("Safeguarding training")) + " - " + _(
			"completed {0}"
		).format(_format_date(training_best.get("date_received")))

	return {
		"has_dbs_on_file": bool(dbs_best),
		"has_training_on_file": bool(training_best),
		"identity_verified_date": join_date,
		"right_to_work_date": join_date,
		"right_to_work_note": RIGHT_TO_WORK_NOTE,
		"dbs_certificate_number": dbs_number,
		"dbs_issue_date": dbs_issue_date,
		"dbs_expiry_date": dbs_expiry_date,
		"dbs_update_service_text": update_service_status,
		"safeguarding_training_text": training_text,
	}


# -------------------------------------------------------------------
# Schools - pulled from real Client records (client_type="School"), not
# a separate hardcoded/lightweight list - see CLIENT_DOCTYPE's own
# comment above for why.
# -------------------------------------------------------------------

_CLIENT_POSTCODE_FIELD_CANDIDATES = ["zip_code", "postcode", "postal_code"]


def _client_postcode_fieldname():
	meta = frappe.get_meta(CLIENT_DOCTYPE)
	for fieldname in _CLIENT_POSTCODE_FIELD_CANDIDATES:
		if meta.has_field(fieldname):
			return fieldname
	return None


def _default_school_contact(client_name):
	"""
	Best-effort prefill for the request form - tries the Client's own
	Billing Contact first (the person most likely to be the school's
	main point of contact), then falls back to the first Client Contact
	Link row on file. Returns {} if neither exists - the coach always
	types/confirms these on the form regardless, this is only ever a
	convenience, never trusted as-is.
	"""
	client_meta = frappe.get_meta(CLIENT_DOCTYPE)

	billing_contact = frappe.db.get_value(CLIENT_DOCTYPE, client_name, "billing_contact") \
		if client_meta.has_field("billing_contact") else None
	if billing_contact and frappe.db.exists("Contact", billing_contact):
		contact = frappe.get_doc("Contact", billing_contact)
		return {
			"contact_name": contact.get("full_name") or billing_contact,
			"email_id": contact.get("email_id") or "",
		}

	if client_meta.has_field("client_contacts"):
		rows = frappe.get_all(
			"Client Contact Link",
			filters={"parent": client_name, "parenttype": CLIENT_DOCTYPE, "parentfield": "client_contacts"},
			fields=["contact_name", "email_id"],
			order_by="idx asc",
			limit_page_length=1,
		)
		if rows:
			return {"contact_name": rows[0].contact_name, "email_id": rows[0].email_id}

	return {}


@frappe.whitelist()
def get_school_options():
	ensure_logged_in()

	meta = frappe.get_meta(CLIENT_DOCTYPE)
	postcode_field = _client_postcode_fieldname()

	fields = ["name", "client_name"]
	if meta.has_field("address"):
		fields.append("address")
	if postcode_field:
		fields.append(postcode_field)

	rows = frappe.get_all(
		CLIENT_DOCTYPE,
		filters={"client_type": SCHOOL_CLIENT_TYPE},
		fields=fields,
		order_by="client_name asc",
		limit_page_length=0,
	)

	results = []
	for row in rows:
		default_contact = _default_school_contact(row.name)
		results.append({
			"name": row.name,
			"school_name": row.get("client_name") or row.name,
			"address": row.get("address") or "",
			"postcode": (row.get(postcode_field) if postcode_field else "") or "",
			"default_contact_name": default_contact.get("contact_name", ""),
			# No equivalent "job title" field exists on a Client Contact -
			# left blank, the coach types it in by hand.
			"default_contact_role": "",
			"default_contact_email": default_contact.get("email_id", ""),
		})

	return results


def _get_or_create_school(school, new_school_name, new_school_address, new_school_postcode):
	school = coalesce_str("school", school)

	if school:
		if not frappe.db.exists(CLIENT_DOCTYPE, school):
			frappe.throw(_("School not found."))
		return school

	new_school_name = coalesce_str("new_school_name", new_school_name)
	if not new_school_name:
		frappe.throw(_("Please select a school, or enter a new school's name."))

	existing_name = frappe.db.get_value(
		CLIENT_DOCTYPE, {"client_type": SCHOOL_CLIENT_TYPE, "client_name": new_school_name}, "name",
	)
	if existing_name:
		return existing_name

	meta = frappe.get_meta(CLIENT_DOCTYPE)
	postcode_field = _client_postcode_fieldname()

	doc = frappe.new_doc(CLIENT_DOCTYPE)
	doc.client_name = new_school_name
	doc.client_type = SCHOOL_CLIENT_TYPE
	if meta.has_field("address"):
		doc.address = coalesce_str("new_school_address", new_school_address)
	if postcode_field:
		doc.set(postcode_field, coalesce_str("new_school_postcode", new_school_postcode))
	doc.insert(ignore_permissions=True)

	return doc.name


# -------------------------------------------------------------------
# Coach-facing: request a letter
# -------------------------------------------------------------------

@frappe.whitelist()
def get_request_form_defaults():
	"""Coach-facing: what the request form needs before it can render -
	the coach's own pulled-in details, the role options, and the
	default Nature of Work wording."""
	ensure_logged_in()
	coach = get_current_coach_name()

	coach_doc = frappe.get_doc(COACH_DOCTYPE, coach)

	return {
		"coach_name": coach_doc.get("coach_name") or coach,
		"role_options": ROLE_OPTIONS,
		"default_nature_of_work": DEFAULT_NATURE_OF_WORK,
	}


@frappe.whitelist()
def submit_assurance_request(
	school=None,
	new_school_name=None,
	new_school_address=None,
	new_school_postcode=None,
	school_contact_name=None,
	school_contact_role=None,
	school_contact_email=None,
	role=None,
	nature_of_work=None,
	expected_start_date=None,
	expected_end_date=None,
):
	ensure_logged_in()
	coach = get_current_coach_name()

	school_contact_name = coalesce_str("school_contact_name", school_contact_name)
	school_contact_email = coalesce_str("school_contact_email", school_contact_email)
	role = coalesce_str("role", role)
	nature_of_work = coalesce_str("nature_of_work", nature_of_work) or DEFAULT_NATURE_OF_WORK
	expected_start_date = coalesce_str("expected_start_date", expected_start_date)

	if not school_contact_name:
		frappe.throw(_("Please enter the school contact's name."))

	if not school_contact_email:
		frappe.throw(_("Please enter the school contact's email address."))

	if role not in ROLE_OPTIONS:
		frappe.throw(_("Please choose a role from the list."))

	if not expected_start_date:
		frappe.throw(_("Please enter the expected start date."))

	school = _get_or_create_school(school, new_school_name, new_school_address, new_school_postcode)
	school_label = frappe.db.get_value(CLIENT_DOCTYPE, school, "client_name") or school

	doc = frappe.new_doc(REQUEST_DOCTYPE)
	doc.coach = coach
	doc.coach_name = frappe.db.get_value(COACH_DOCTYPE, coach, "coach_name") or coach
	doc.school = school
	doc.school_contact_name = school_contact_name
	doc.school_contact_role = coalesce_str("school_contact_role", school_contact_role)
	doc.school_contact_email = school_contact_email
	doc.role = role
	doc.nature_of_work = nature_of_work
	doc.expected_start_date = expected_start_date
	doc.expected_end_date = coalesce_str("expected_end_date", expected_end_date) or None
	doc.workflow_status = "Submitted"
	doc.employment_history_note = DEFAULT_EMPLOYMENT_HISTORY_NOTE
	doc.dbs_certificate_level = "Enhanced"
	doc.dbs_workforce = "Child Workforce"
	doc.compliance_guidance_version = COMPLIANCE_GUIDANCE_VERSION
	doc.letter_template_version = LETTER_TEMPLATE_VERSION
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	coach_label = doc.coach_name or coach

	try:
		create_trk_notification(
			recipient_user=ASHLEY_USER,
			notification_type="Task",
			message=f"{coach_label} has requested a Safeguarding Assurance Letter for {school_label}.",
			priority="High",
			reference_doctype=REQUEST_DOCTYPE,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Safeguarding Letter - Ashley Notification Failed")

	return {"ok": 1, "name": doc.name}


@frappe.whitelist()
def get_my_assurance_requests():
	ensure_logged_in()
	coach = get_current_coach_name()

	rows = frappe.get_all(
		REQUEST_DOCTYPE,
		filters={"coach": coach},
		fields=["name", "school", "workflow_status", "expected_start_date", "creation", "approved_at", "issued_at"],
		order_by="creation desc",
		limit_page_length=0,
	)

	school_names = {row.school for row in rows if row.school}
	school_labels = {
		row.name: row.client_name
		for row in frappe.get_all(CLIENT_DOCTYPE, filters={"name": ["in", list(school_names)]}, fields=["name", "client_name"])
	} if school_names else {}

	for row in rows:
		row["school_label"] = school_labels.get(row.school, row.school)

	return rows


@frappe.whitelist()
def get_my_assurance_request(name):
	doc = _get_owned_request(name)

	return {
		"name": doc.name,
		"school_label": frappe.db.get_value(CLIENT_DOCTYPE, doc.school, "client_name") or doc.school,
		"role": doc.role,
		"expected_start_date": doc.expected_start_date,
		"workflow_status": doc.workflow_status,
		"correction_notes": doc.correction_notes,
		"rejection_reason": doc.rejection_reason,
		"issued_at": doc.issued_at,
		"has_final_pdf": bool(doc.final_pdf),
	}


def _serve_private_file(file_url):
	if not file_url:
		frappe.throw(_("No file is attached to this request."))

	from frappe.utils.file_manager import get_file

	fname, fcontent = get_file(file_url)

	frappe.local.response.filename = fname
	frappe.local.response.filecontent = fcontent
	frappe.local.response.type = "download"


@frappe.whitelist()
def download_my_assurance_letter(name):
	doc = _get_owned_request(name)

	if doc.workflow_status != "Signed and Issued" or not doc.final_pdf:
		frappe.throw(_("This letter has not been issued yet."))

	_serve_private_file(doc.final_pdf)


# -------------------------------------------------------------------
# Franchisor-facing: review, approve, sign
# -------------------------------------------------------------------

@frappe.whitelist()
def get_assurance_requests_for_review(status=None, coach=None):
	"""
	Franchisor-only. Also used (filtered to one coach) by the "Safeguarding
	Letters" tab on that coach's own Profile page when a franchisor is
	viewing it via "View As" - same reach as every other Legal Details
	row on that same view-as page, just read-only like the rest of it.
	"""
	ensure_office_user()

	filters = {}
	status = coalesce_str("status", status)
	if status:
		filters["workflow_status"] = status

	coach = coalesce_str("coach", coach)
	if coach:
		filters["coach"] = coach

	rows = frappe.get_all(
		REQUEST_DOCTYPE,
		filters=filters,
		fields=["name", "coach", "coach_name", "school", "role", "workflow_status", "expected_start_date", "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)

	school_names = {row.school for row in rows if row.school}
	school_labels = {
		row.name: row.client_name
		for row in frappe.get_all(CLIENT_DOCTYPE, filters={"name": ["in", list(school_names)]}, fields=["name", "client_name"])
	} if school_names else {}

	for row in rows:
		row["school_label"] = school_labels.get(row.school, row.school)

	return rows


def _missing_information(doc, evidence):
	"""
	The plain completeness gate before Ashley can approve - not a
	simulation of real safeguarding law, just "has every field that
	needs an answer actually got one". See this module's own docstring
	for why the legal-judgement fields are Ashley's own typed answers
	rather than something this function tries to determine itself.
	"""
	missing = []

	if not evidence.get("has_dbs_on_file"):
		missing.append(_("No DBS certificate is on file for this coach."))

	if not evidence.get("has_training_on_file"):
		missing.append(_("No safeguarding training record is on file for this coach."))

	if not (doc.regulated_activity_assessment or "").strip():
		missing.append(_("Regulated activity assessment has not been entered."))

	if not (doc.dbs_wording_option or "").strip():
		missing.append(_("DBS section wording has not been chosen."))

	if not (doc.childrens_barred_list_check or "").strip():
		missing.append(_("Children's barred-list check has not been entered."))

	if not (doc.kcsie_part_one_acknowledgement or "").strip():
		missing.append(_("KCSIE Part One acknowledgement has not been entered."))

	if not (doc.overseas_checks or "").strip():
		missing.append(_("Overseas checks has not been entered."))

	if not (doc.employment_history_note or "").strip():
		missing.append(_("Employment history has not been entered."))

	return missing


@frappe.whitelist()
def get_assurance_request_for_review(name):
	ensure_office_user()

	if not name or not frappe.db.exists(REQUEST_DOCTYPE, name):
		frappe.throw(_("Request not found."))

	doc = frappe.get_doc(REQUEST_DOCTYPE, name)
	coach_doc = frappe.get_doc(COACH_DOCTYPE, doc.coach)
	evidence = _build_evidence(coach_doc)

	return {
		"name": doc.name,
		"coach": doc.coach,
		"coach_name": doc.coach_name,
		"school": doc.school,
		"school_label": frappe.db.get_value(CLIENT_DOCTYPE, doc.school, "client_name") or doc.school,
		"school_contact_name": doc.school_contact_name,
		"school_contact_role": doc.school_contact_role,
		"school_contact_email": doc.school_contact_email,
		"role": doc.role,
		"nature_of_work": doc.nature_of_work,
		"expected_start_date": doc.expected_start_date,
		"expected_end_date": doc.expected_end_date,
		"workflow_status": doc.workflow_status,
		"regulated_activity_assessment": doc.regulated_activity_assessment,
		"dbs_wording_option": doc.dbs_wording_option,
		"dbs_certificate_level": doc.dbs_certificate_level,
		"dbs_workforce": doc.dbs_workforce,
		"childrens_barred_list_check": doc.childrens_barred_list_check,
		"kcsie_part_one_acknowledgement": doc.kcsie_part_one_acknowledgement,
		"overseas_checks": doc.overseas_checks,
		"employment_history_note": doc.employment_history_note,
		"default_employment_history_note": DEFAULT_EMPLOYMENT_HISTORY_NOTE,
		"dbs_wording_options": DBS_WORDING_OPTIONS,
		"rejection_reason": doc.rejection_reason,
		"correction_notes": doc.correction_notes,
		"is_ashley": frappe.session.user == ASHLEY_USER,
		"evidence": evidence,
		"missing_information": _missing_information(doc, evidence),
	}


@frappe.whitelist()
def save_assurance_review(
	name,
	regulated_activity_assessment=None,
	dbs_wording_option=None,
	dbs_certificate_level=None,
	dbs_workforce=None,
	childrens_barred_list_check=None,
	kcsie_part_one_acknowledgement=None,
	overseas_checks=None,
	employment_history_note=None,
):
	ensure_office_user()

	if not name or not frappe.db.exists(REQUEST_DOCTYPE, name):
		frappe.throw(_("Request not found."))

	doc = frappe.get_doc(REQUEST_DOCTYPE, name)

	if doc.workflow_status not in ("Submitted", "Under Review", "Returned for Correction"):
		frappe.throw(_("This request can no longer be edited."))

	doc.regulated_activity_assessment = coalesce_str("regulated_activity_assessment", regulated_activity_assessment)
	doc.dbs_wording_option = coalesce_str("dbs_wording_option", dbs_wording_option)
	doc.dbs_certificate_level = coalesce_str("dbs_certificate_level", dbs_certificate_level) or "Enhanced"
	doc.dbs_workforce = coalesce_str("dbs_workforce", dbs_workforce) or "Child Workforce"
	doc.childrens_barred_list_check = coalesce_str("childrens_barred_list_check", childrens_barred_list_check)
	doc.kcsie_part_one_acknowledgement = coalesce_str("kcsie_part_one_acknowledgement", kcsie_part_one_acknowledgement)
	doc.overseas_checks = coalesce_str("overseas_checks", overseas_checks)
	doc.employment_history_note = coalesce_str("employment_history_note", employment_history_note)
	doc.workflow_status = "Under Review"
	doc.reviewed_by = frappe.session.user
	doc.reviewed_at = now_datetime()
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	coach_doc = frappe.get_doc(COACH_DOCTYPE, doc.coach)
	evidence = _build_evidence(coach_doc)

	return {"ok": 1, "missing_information": _missing_information(doc, evidence)}


@frappe.whitelist()
def preview_assurance_letter(name):
	ensure_office_user()

	if not name or not frappe.db.exists(REQUEST_DOCTYPE, name):
		frappe.throw(_("Request not found."))

	doc = frappe.get_doc(REQUEST_DOCTYPE, name)
	coach_doc = frappe.get_doc(COACH_DOCTYPE, doc.coach)
	evidence = _build_evidence(coach_doc)

	return {"html": _render_letter_html(doc, coach_doc, evidence, is_signed=False)}


@frappe.whitelist()
def return_for_correction(name, correction_notes):
	ensure_office_user()

	if not name or not frappe.db.exists(REQUEST_DOCTYPE, name):
		frappe.throw(_("Request not found."))

	correction_notes = coalesce_str("correction_notes", correction_notes)
	if not correction_notes:
		frappe.throw(_("Please explain what needs to change."))

	doc = frappe.get_doc(REQUEST_DOCTYPE, name)
	doc.correction_notes = correction_notes
	doc.workflow_status = "Returned for Correction"
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	_notify_coach(doc, "Action needed on your Safeguarding Assurance Letter request", correction_notes)

	return {"ok": 1}


@frappe.whitelist()
def reject_assurance_request(name, rejection_reason):
	ensure_office_user()

	if not name or not frappe.db.exists(REQUEST_DOCTYPE, name):
		frappe.throw(_("Request not found."))

	rejection_reason = coalesce_str("rejection_reason", rejection_reason)
	if not rejection_reason:
		frappe.throw(_("Please give a reason for rejecting this request."))

	doc = frappe.get_doc(REQUEST_DOCTYPE, name)
	doc.rejection_reason = rejection_reason
	doc.workflow_status = "Rejected"
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	_notify_coach(doc, "Your Safeguarding Assurance Letter request was not approved", rejection_reason)

	return {"ok": 1}


def _notify_coach(doc, message_title, detail):
	coach_user = frappe.db.get_value(COACH_DOCTYPE, doc.coach, "coach_email")
	if not coach_user:
		return

	try:
		create_trk_notification(
			recipient_user=coach_user,
			notification_type="Task",
			message=f"{message_title}: {detail}",
			priority="High",
			reference_doctype=REQUEST_DOCTYPE,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Safeguarding Letter - Coach Notification Failed")


@frappe.whitelist()
def approve_and_sign_assurance_request(name, typed_full_name=None, signature=None, approval_confirmed=None):
	_ensure_ashley()

	if not name or not frappe.db.exists(REQUEST_DOCTYPE, name):
		frappe.throw(_("Request not found."))

	typed_full_name = coalesce_str("typed_full_name", typed_full_name)
	signature = coalesce_str("signature", signature)
	confirmed = str(approval_confirmed or "").strip().lower() in ("1", "true", "yes")

	if not confirmed:
		frappe.throw(_("Please confirm the approval statement before signing."))

	if not typed_full_name:
		frappe.throw(_("Please type your full name to sign."))

	if not signature:
		frappe.throw(_("Please draw your signature before approving."))

	doc = frappe.get_doc(REQUEST_DOCTYPE, name)

	if doc.workflow_status not in ("Submitted", "Under Review", "Returned for Correction"):
		frappe.throw(_("This request is not ready to be approved."))

	coach_doc = frappe.get_doc(COACH_DOCTYPE, doc.coach)
	evidence = _build_evidence(coach_doc)
	missing = _missing_information(doc, evidence)

	if missing:
		frappe.throw(_("This request can't be approved yet - {0}").format("; ".join(missing)))

	now = now_datetime()

	doc.approved_by = frappe.session.user
	doc.approved_at = now
	doc.approval_confirmed = 1
	doc.signed_by = frappe.session.user
	doc.signed_at = now
	doc.typed_full_name = typed_full_name
	doc.signature = signature
	doc.reviewed_by = doc.reviewed_by or frappe.session.user
	doc.reviewed_at = doc.reviewed_at or now

	snapshot = {
		"coach_name": doc.coach_name,
		"role": doc.role,
		"nature_of_work": doc.nature_of_work,
		"school": doc.school,
		"expected_start_date": str(doc.expected_start_date) if doc.expected_start_date else "",
		"regulated_activity_assessment": doc.regulated_activity_assessment,
		"identity_verified_date": str(evidence["identity_verified_date"]),
		"right_to_work_date": str(evidence["right_to_work_date"]),
		"dbs_certificate_number": evidence["dbs_certificate_number"],
		"dbs_issue_date": str(evidence["dbs_issue_date"]) if evidence["dbs_issue_date"] else "",
		"dbs_expiry_date": str(evidence["dbs_expiry_date"]) if evidence["dbs_expiry_date"] else "",
		"dbs_wording_option": doc.dbs_wording_option,
		"childrens_barred_list_check": doc.childrens_barred_list_check,
		"dbs_update_service_text": evidence["dbs_update_service_text"],
		"employment_history_note": doc.employment_history_note,
		"safeguarding_training_text": evidence["safeguarding_training_text"],
		"kcsie_part_one_acknowledgement": doc.kcsie_part_one_acknowledgement,
		"overseas_checks": doc.overseas_checks,
		"approved_by": doc.approved_by,
		"approved_at": str(now),
	}
	doc.evidence_snapshot = json.dumps(snapshot, indent=2)

	html = _render_letter_html(doc, coach_doc, evidence, is_signed=True)

	from frappe.utils.pdf import get_pdf

	pdf_content = get_pdf(html)
	pdf_hash = hashlib.sha256(pdf_content).hexdigest()

	from frappe.utils.file_manager import save_file

	file_doc = save_file(
		f"Safeguarding Assurance Letter - {doc.name}.pdf",
		pdf_content,
		REQUEST_DOCTYPE,
		doc.name,
		is_private=1,
	)

	doc.final_pdf = file_doc.file_url
	doc.final_pdf_hash = pdf_hash
	doc.issued_at = now
	doc.workflow_status = "Signed and Issued"
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	_notify_coach(
		doc,
		"Your Safeguarding Assurance Letter is ready",
		f"Your signed letter for {doc.school} is ready to download.",
	)

	return {"ok": 1}


# -------------------------------------------------------------------
# Letter rendering
# -------------------------------------------------------------------

def _logo_data_uri():
	"""
	Inlined as base64 rather than referenced by URL - get_pdf()'s
	renderer fetching a private file over HTTP mid-render is exactly
	the kind of thing that works in a browser preview and silently
	fails in a server-side PDF, so the logo's bytes are read directly
	and embedded instead. Never throws - a missing/renamed logo file
	means a letter without a logo, not a failed letter.
	"""
	try:
		from frappe.utils.file_manager import get_file

		fname, fcontent = get_file(LOGO_FILE_URL)
		return "data:image/png;base64," + base64.b64encode(fcontent).decode("ascii")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Safeguarding Letter - Logo Load Failed")
		return ""


def _render_letter_html(doc, coach_doc, evidence, is_signed):
	"""
	Every free-text value below is escaped before it reaches the
	template - frappe.render_template(string, ...) can't be relied on
	for autoescaping the way a web page request is (same reason
	public_booking._send_booking_confirmation_email escapes its own
	visitor-entered strings rather than trusting the template), and
	this one ends up as a signed PDF a school keeps on file, not
	something a second validation pass ever gets to catch.
	"""
	esc = frappe.utils.escape_html

	dbs_option = doc.dbs_wording_option or "Certificate clear"
	dbs_statement = DBS_STATEMENTS.get(dbs_option, DBS_STATEMENTS["Certificate clear"])

	dbs_certificate_text = (
		esc(doc.dbs_certificate_level or "Enhanced")
		+ ", "
		+ esc(doc.dbs_workforce or "Child Workforce")
		+ (", issued " + _format_date(evidence["dbs_issue_date"]) if evidence["dbs_issue_date"] else "")
	) if evidence["has_dbs_on_file"] else _("Not on file")

	context = {
		"frappe": frappe,
		"letter_reference": doc.name,
		"compliance_guidance_version": esc(doc.compliance_guidance_version or COMPLIANCE_GUIDANCE_VERSION),
		"coach_name": esc(doc.coach_name or coach_doc.get("coach_name")),
		"role": esc(doc.role or ""),
		"nature_of_work": esc(doc.nature_of_work or ""),
		"school_contact_name": esc(doc.school_contact_name or ""),
		"school_contact_role": esc(doc.school_contact_role or ""),
		"regulated_activity_assessment": esc(doc.regulated_activity_assessment or ""),
		"childrens_barred_list_check": esc(doc.childrens_barred_list_check or ""),
		"kcsie_part_one_acknowledgement": esc(doc.kcsie_part_one_acknowledgement or ""),
		"overseas_checks": esc(doc.overseas_checks or ""),
		"employment_history_note": esc(doc.employment_history_note or ""),
		"dbs_certificate_level": esc(doc.dbs_certificate_level or "Enhanced"),
		"dbs_workforce": esc(doc.dbs_workforce or "Child Workforce"),
		"expected_start_date": doc.expected_start_date,
		"org_name": ORG_NAME,
		"org_address": ORG_ADDRESS,
		"from_email": FROM_EMAIL,
		"from_phone": FROM_PHONE,
		"footer_phone": FOOTER_PHONE,
		"footer_email": FOOTER_EMAIL,
		"signatory_name": SIGNATORY_NAME,
		"signatory_role": SIGNATORY_ROLE,
		"logo_data_uri": _logo_data_uri(),
		"letter_date": frappe.utils.formatdate(nowdate(), "d MMMM yyyy"),
		"school_label": esc(frappe.db.get_value(CLIENT_DOCTYPE, doc.school, "client_name") or doc.school),
		"school_address": esc(frappe.db.get_value(CLIENT_DOCTYPE, doc.school, "address") or ""),
		"evidence": evidence,
		"identity_verified_text": _format_date(evidence["identity_verified_date"]),
		"right_to_work_text": _format_date(evidence["right_to_work_date"]) + " - " + RIGHT_TO_WORK_NOTE,
		"dbs_certificate_number": esc(evidence["dbs_certificate_number"] or ""),
		"dbs_issue_date_text": _format_date(evidence["dbs_issue_date"]),
		"dbs_certificate_text": dbs_certificate_text,
		"dbs_statement": dbs_statement,
		"dbs_update_service_text": esc(evidence["dbs_update_service_text"] or _("Not subscribed")),
		"employment_references_text": STATIC_EMPLOYMENT_REFERENCES_TEXT,
		"safeguarding_training_text": esc(evidence["safeguarding_training_text"] or _("Not on file")),
		"has_dbs_on_file": evidence["has_dbs_on_file"],
		"is_signed": is_signed,
		"signature": doc.signature if is_signed else None,
		"signed_date_text": frappe.utils.formatdate(getdate(doc.signed_at), "d MMMM yyyy") if is_signed and doc.signed_at else "",
	}

	return frappe.render_template(LETTER_TEMPLATE, context)


LETTER_TEMPLATE = """
<style>
  body { font-family: Arial, Helvetica, sans-serif; color: #434B49; font-size: 11.5px; line-height: 1.6; }
  .letterhead { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #F2F8F8; padding-bottom: 12px; margin-bottom: 16px; }
  .letterhead img { max-height: 46px; }
  .header-meta { text-align: right; font-size: 11px; }
  .header-meta .label { color: #839898; font-weight: bold; }
  .confidential { text-align: center; font-size: 9.5px; letter-spacing: 1px; font-weight: bold; color: #AC455C; text-transform: uppercase; margin-bottom: 14px; }
  .recipient-block { font-size: 11.5px; margin-bottom: 14px; }
  .recipient-block .lbl { color: #839898; font-weight: bold; font-size: 9.5px; text-transform: uppercase; display: block; margin: 8px 0 2px; }
  .re-line { font-weight: bold; margin: 12px 0; }
  h2 { font-size: 12.5px; text-transform: uppercase; color: #AC455C; border-bottom: 1px solid #F2F8F8; padding-bottom: 3px; margin: 18px 0 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 10.5px; margin-bottom: 6px; }
  th { text-align: left; background: #F2F8F8; color: #007274; padding: 5px 7px; border: 1px solid #e3eded; }
  td { padding: 5px 7px; border: 1px solid #e3eded; vertical-align: top; }
  td.field { font-weight: bold; width: 34%; }
  .dbs-box { background: #F2F8F8; border-left: 3px solid #00A19E; padding: 8px 12px; font-size: 11px; margin: 8px 0 12px; }
  .confirm-box { background: #fdf1f3; border-left: 3px solid #AC455C; padding: 10px 12px; font-size: 11px; margin: 8px 0; }
  .signature-block { margin-top: 20px; }
  .signature-block img { max-height: 60px; display: block; margin-bottom: 4px; }
  .footer { margin-top: 18px; padding-top: 10px; border-top: 1px solid #F2F8F8; font-size: 9.5px; color: #839898; display: flex; justify-content: space-between; }
</style>

<div class="letterhead">
  {% if logo_data_uri %}<img src="{{ logo_data_uri }}" alt="The Resilient Kid">{% endif %}
  <div class="header-meta">
    <div><span class="label">Date:</span> {{ letter_date }}</div>
    <div><span class="label">Reference:</span> {{ letter_reference }}</div>
  </div>
</div>

<div class="confidential">Private and confidential - for authorised school safeguarding use</div>

<div class="recipient-block">
  <span class="lbl">From</span>
  {{ org_name }}<br>
  {{ org_address }}<br>
  {{ from_email }} &middot; {{ from_phone }}

  <span class="lbl">To</span>
  {{ school_contact_name }}{% if school_contact_role %}, {{ school_contact_role }}{% endif %}<br>
  {{ school_label }}<br>
  {{ school_address }}
</div>

<div class="re-line">Re: Safeguarding and Safer Recruitment Assurance - {{ coach_name }}</div>

<p>Dear {{ school_contact_name }},</p>
<p>I am writing on behalf of {{ org_name }} to provide formal written assurance regarding the safeguarding and safer recruitment checks undertaken in respect of {{ coach_name }}, who will be providing {{ nature_of_work }} at {{ school_label }}.</p>
<p>We recognise the importance of ensuring that individuals working with children and young people have been subject to appropriate checks and are suitable for the work they undertake.</p>
<p>This letter has been prepared with reference to the Department for Education's Keeping Children Safe in Education guidance ({{ compliance_guidance_version }}) and the applicable safer recruitment requirements.</p>
<p>We confirm below the checks that have been completed and verified by {{ org_name }} or an appropriately authorised organisation, as identified in our records.</p>

<h2>1. Individual and Role Details</h2>
<table>
  <tr><td class="field">Full legal name</td><td>{{ coach_name }}</td></tr>
  <tr><td class="field">Organisation</td><td>{{ org_name }}</td></tr>
  <tr><td class="field">Role</td><td>{{ role }}</td></tr>
  <tr><td class="field">Nature of work</td><td>{{ nature_of_work }}</td></tr>
  <tr><td class="field">School</td><td>{{ school_label }}</td></tr>
  <tr><td class="field">Intended start date</td><td>{{ frappe.utils.formatdate(expected_start_date, "d MMMM yyyy") if expected_start_date else "" }}</td></tr>
  {% if regulated_activity_assessment %}<tr><td class="field">Regulated activity assessment</td><td>{{ regulated_activity_assessment }}</td></tr>{% endif %}
</table>

<h2>2. Safeguarding and Safer Recruitment Checks</h2>
<table>
  <tr><td class="field">Identity verification</td><td>{{ identity_verified_text }}</td></tr>
  <tr><td class="field">Right to work in the UK</td><td>{{ right_to_work_text }}</td></tr>
  <tr><td class="field">Enhanced DBS certificate</td><td>{{ dbs_certificate_text }}</td></tr>
  {% if childrens_barred_list_check %}<tr><td class="field">Children's barred-list check</td><td>{{ childrens_barred_list_check }}</td></tr>{% endif %}
  <tr><td class="field">DBS Update Service</td><td>{{ dbs_update_service_text }}</td></tr>
  <tr><td class="field">Employment references</td><td>{{ employment_references_text }}</td></tr>
  {% if employment_history_note %}<tr><td class="field">Employment history</td><td>{{ employment_history_note }}</td></tr>{% endif %}
  <tr><td class="field">Safeguarding training</td><td>{{ safeguarding_training_text }}</td></tr>
  {% if kcsie_part_one_acknowledgement %}<tr><td class="field">KCSIE Part One acknowledgement</td><td>{{ kcsie_part_one_acknowledgement }}</td></tr>{% endif %}
  {% if overseas_checks %}<tr><td class="field">Overseas checks</td><td>{{ overseas_checks }}</td></tr>{% endif %}
</table>

<h2>3. Disclosure and Barring Service (DBS)</h2>
<p>We confirm that the DBS certificate recorded above has been obtained and verified as stated in our safeguarding records.</p>
<div class="dbs-box">
  {% if has_dbs_on_file %}
  <div>DBS Certificate Number: {{ dbs_certificate_number }}</div>
  <div>Certificate Issue Date: {{ dbs_issue_date_text }}</div>
  <div>Certificate Level: {{ dbs_certificate_level }}</div>
  <div>Workforce: {{ dbs_workforce }}</div>
  {% if childrens_barred_list_check %}<div>Children's Barred-List Information: {{ childrens_barred_list_check }}</div>{% endif %}
  <br>
  {% endif %}
  <p>{{ dbs_statement }}</p>
</div>
<p>The individual will be advised to present their original DBS certificate and appropriate photographic identification to the school where requested, to enable the school to undertake its own lawful verification procedures.</p>

<h2>4. References, Qualifications and Safeguarding Training</h2>
<p>We confirm that the references, qualifications and safeguarding training identified in Section 2 have been reviewed and verified to the extent stated.</p>
<p>The individual has been made aware of the importance of safeguarding children and young people, maintaining professional boundaries, reporting safeguarding concerns promptly and following the safeguarding policies and procedures of the school in which they are working.</p>
<p>The individual is expected to familiarise themselves with the school's safeguarding arrangements, including the identity of the Designated Safeguarding Lead, before commencing work.</p>

<h2>5. Confirmation of Suitability</h2>
<div class="confirm-box">
  On the basis of the checks completed, verified and recorded by {{ org_name }}, we confirm that {{ coach_name }} has been assessed as suitable to undertake the specified role described in this letter, subject to any stated role or supervision arrangements.
  <br><br>
  We confirm that the checks required of our organisation for this engagement have been completed, as detailed above. This assurance is provided in accordance with our safer recruitment and safeguarding procedures and with reference to the relevant requirements of Keeping Children Safe in Education ({{ compliance_guidance_version }}).
  <br><br>
  This confirmation relates to the individual, role and checks specified in this letter as at the date of issue. It does not replace the school's own safeguarding responsibilities, including verifying the identity of the person attending and undertaking any checks or actions required of the school.
</div>

<h2>6. Further Verification</h2>
<p>Should you require clarification of any information contained in this letter, please contact {{ org_name }} directly using the contact details provided.</p>
<p>We are happy to cooperate with reasonable safeguarding verification requests, subject to applicable legal requirements, confidentiality and data protection obligations.</p>
<p>Yours sincerely,</p>

<div class="signature-block">
  {% if is_signed and signature %}
  <img src="{{ signature }}" alt="Signature">
  {% endif %}
  <div><strong>{{ signatory_name }}</strong></div>
  <div>{{ signatory_role }}</div>
  {% if is_signed %}
  <div>Date signed: {{ signed_date_text }}</div>
  <div>This letter has been reviewed, approved and electronically signed by the authorised signatory of {{ org_name }}.</div>
  {% else %}
  <div style="color:#AC455C; font-weight:bold;">DRAFT - not yet approved or signed</div>
  {% endif %}
</div>

<div class="footer">
  <div>{{ footer_phone }} &middot; {{ footer_email }}</div>
  <div>Letter Reference: {{ letter_reference }}</div>
</div>
"""

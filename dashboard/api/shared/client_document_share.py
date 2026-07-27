"""
Coach-initiated sharing of a Client Resource Practice Document with a
client's authorised contact, and the guest-facing secure portal link that
recipient then opens at /client-document/<token>.

Client Document Share is an audit trail of what was sent and what the
client did with it - distinct from Coach Document Requirement, which
tracks what the coach themselves must do. Once a share has been sent, its
recipient (client/recipient_contact/recipient_email) can never change -
revoke it and create a new Client Document Share instead (enforced in the
doctype's before_save()).
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, get_url, escape_html

from dashboard.api.shared.permissions import (
	ensure_logged_in,
	ensure_client_access,
	is_office_user,
	get_current_coach_name,
)
from dashboard.api.shared.client_details import get_client_contacts_for_context
from dashboard.api.shared.practice_documents import coach_can_see_resource

SHARE_DOCTYPE = "Client Document Share"
PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"

HISTORY_FIELDS = [
	"name",
	"practice_document",
	"document_title",
	"client",
	"recipient_name",
	"recipient_email",
	"recipient_type",
	"delivery_method",
	"status",
	"shared_on",
	"sent_on",
	"viewed_on",
	"completed_on",
	"link_revoked",
	"access_token",
	"client_acknowledged",
]


# ---------------------------------------------------------------------------
# Coach-side: clients, recipients, and creating/managing shares
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_share_target_clients():
	"""Only clients the current user is already authorised to access -
	reuses the same coach-client permission model as the Clients page."""
	from dashboard.api.shared.clients import get_clients

	return get_clients()


def _bucket_recipient_type(relationship, is_billing_contact):
	text = (relationship or "").lower()

	if is_billing_contact or "billing" in text:
		return "Billing Contact"
	if "parent" in text or "guardian" in text:
		return "Parent/Guardian"
	if "school" in text:
		return "School Contact"
	if "company" in text:
		return "Company Contact"

	return "Other Authorised Contact"


def _get_share_recipients_for_client(client_doc):
	recipients = []

	if client_doc.get("client_type") == "Adult" and client_doc.get("email"):
		recipients.append(
			{
				"recipient_type": "Adult Client",
				"contact": "",
				"name": client_doc.get("full_name") or client_doc.name,
				"email": client_doc.get("email"),
			}
		)

	for row in get_client_contacts_for_context(client_doc):
		if not row.get("email"):
			continue

		recipients.append(
			{
				"recipient_type": _bucket_recipient_type(
					row.get("relationship"), row.get("is_billing_contact")
				),
				"contact": row.get("contact") or "",
				"name": row.get("display_name") or row.get("email"),
				"email": row.get("email"),
			}
		)

	return recipients


@frappe.whitelist()
def get_share_recipients(client_name):
	client_doc = ensure_client_access(client_name)
	return _get_share_recipients_for_client(client_doc)


def _find_recipient(client_doc, recipient_type, recipient_contact):
	recipient_contact = (recipient_contact or "").strip()

	for candidate in _get_share_recipients_for_client(client_doc):
		if candidate["recipient_type"] != recipient_type:
			continue

		if recipient_contact:
			if candidate.get("contact") == recipient_contact:
				return candidate
		elif not candidate.get("contact"):
			return candidate

	return None


def _ensure_document_shareable(practice_document_name):
	doc = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, practice_document_name)

	if doc.status != "Published" or doc.document_purpose not in ("Client Resource", "Both"):
		frappe.throw(_("This document is not available to share."))

	if not is_office_user():
		coach_name = get_current_coach_name(optional=True)
		row = {"name": doc.name, "all_coaches": doc.all_coaches}
		if not coach_can_see_resource(row, coach_name):
			frappe.throw(_("You do not have access to share this document."), frappe.PermissionError)

	return doc


@frappe.whitelist()
def create_share(practice_document, client, recipient_type, delivery_method, recipient_contact=None, coach_message=None):
	ensure_logged_in()

	coach_name = get_current_coach_name(optional=True)
	if not coach_name and not is_office_user():
		frappe.throw(_("No Coach profile is linked to your user."), frappe.PermissionError)

	client_doc = ensure_client_access(client)
	doc = _ensure_document_shareable(practice_document)

	recipient = _find_recipient(client_doc, recipient_type, recipient_contact)
	if not recipient:
		frappe.throw(_("Choose a recipient for this client."))
	if not recipient.get("email"):
		frappe.throw(_("The selected recipient has no email address on file."))

	share = frappe.new_doc(SHARE_DOCTYPE)
	share.practice_document = doc.name
	share.document_title = doc.document_title
	share.document_code = doc.document_code
	share.document_version = doc.version
	share.coach = coach_name or ""
	share.client = client_doc.name
	share.recipient_type = recipient["recipient_type"]
	share.recipient_contact = recipient.get("contact") or ""
	share.recipient_name = recipient.get("name") or ""
	share.recipient_email = recipient["email"]
	share.delivery_method = delivery_method
	share.coach_message = (coach_message or "").strip()
	share.client_action_required = doc.client_action_required or "None"
	share.insert(ignore_permissions=True)

	_deliver_share(share, doc)

	frappe.db.commit()

	return {"name": share.name, "status": share.status}


def _deliver_share(share, doc):
	try:
		if share.delivery_method == "Secure Portal Link":
			_send_secure_link_email(share, doc)
		elif share.delivery_method == "Email Attachment":
			_send_attachment_email(share, doc)

		share.status = "Sent"
		share.sent_on = now_datetime()
	except Exception:
		frappe.log_error(title="Client Document Share delivery failed", message=frappe.get_traceback())
		share.status = "Failed"

	share.save(ignore_permissions=True)


def _send_secure_link_email(share, doc):
	link = get_url(f"/client-document/{share.access_token}")
	greeting = f"Hi {escape_html(share.recipient_name)}," if share.recipient_name else "Hi,"

	message = f"""
		<p>{greeting}</p>
		{f"<p>{escape_html(share.coach_message)}</p>" if share.coach_message else ""}
		<p>A document has been shared with you securely: <a href="{link}">View document</a></p>
		<p>This link is private to you - please don't forward it on.</p>
	"""

	frappe.sendmail(
		recipients=[share.recipient_email],
		subject=f"A document has been shared with you: {doc.document_title}",
		message=message,
		now=True,
	)


def _send_attachment_email(share, doc):
	attachments = []

	if doc.attached_file:
		from frappe.utils.file_manager import get_file

		fname, fcontent = get_file(doc.attached_file)
		attachments.append({"fname": fname, "fcontent": fcontent})

	greeting = f"Hi {escape_html(share.recipient_name)}," if share.recipient_name else "Hi,"

	message = f"""
		<p>{greeting}</p>
		{f"<p>{escape_html(share.coach_message)}</p>" if share.coach_message else ""}
		<p>Please find attached: {escape_html(doc.document_title)}.</p>
	"""

	frappe.sendmail(
		recipients=[share.recipient_email],
		subject=f"Document: {doc.document_title}",
		message=message,
		attachments=attachments,
		now=True,
	)


def _get_owned_share(share_name):
	ensure_logged_in()

	share = frappe.get_doc(SHARE_DOCTYPE, share_name)

	if not is_office_user():
		coach_name = get_current_coach_name(optional=True)
		if not coach_name or share.coach != coach_name:
			frappe.throw(_("You do not have permission to manage this share."), frappe.PermissionError)

	return share


@frappe.whitelist()
def resend_share(share_name):
	share = _get_owned_share(share_name)

	if share.link_revoked or share.status == "Revoked":
		frappe.throw(_("This share has been revoked. Create a new share instead."))

	doc = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, share.practice_document)
	_deliver_share(share, doc)

	frappe.db.commit()

	return {"status": share.status}


@frappe.whitelist()
def revoke_share(share_name):
	share = _get_owned_share(share_name)

	share.link_revoked = 1
	share.status = "Revoked"
	share.save(ignore_permissions=True)

	frappe.db.commit()

	return {"status": share.status}


@frappe.whitelist()
def get_share_completion(share_name):
	share = _get_owned_share(share_name)

	return {
		"status": share.status,
		"client_acknowledged": share.client_acknowledged,
		"client_typed_name": share.client_typed_name,
		"client_signature": share.client_signature,
		"client_response_on": share.client_response_on,
		"has_completion_record_pdf": bool(share.completion_record_pdf),
		"viewed_on": share.viewed_on,
		"completed_on": share.completed_on,
	}


@frappe.whitelist()
def get_share_completion_pdf(share_name):
	"""Proxies the Completion Record PDF download - a coach isn't a System
	Manager, so the private File's own URL would 403 them directly even for
	their own share (see get_practice_document_file()'s docstring for the
	same issue on the library side)."""
	share = _get_owned_share(share_name)

	if not share.completion_record_pdf:
		frappe.throw(_("No completion record is available for this share."))

	from frappe.utils.file_manager import get_file

	fname, fcontent = get_file(share.completion_record_pdf)

	frappe.local.response.filename = fname
	frappe.local.response.filecontent = fcontent
	frappe.local.response.type = "download"


@frappe.whitelist()
def get_share_history():
	ensure_logged_in()

	filters = {}
	if not is_office_user():
		coach_name = get_current_coach_name(optional=True)
		filters["coach"] = coach_name or "__none__"

	rows = frappe.get_all(
		SHARE_DOCTYPE,
		filters=filters,
		fields=HISTORY_FIELDS,
		order_by="shared_on desc",
		ignore_permissions=True,
	)

	for row in rows:
		client_label = frappe.db.get_value("Client", row["client"], "full_name")
		row["client_label"] = client_label or row["client"]

		token = row.pop("access_token", None)
		if row["delivery_method"] == "Secure Portal Link" and token and not row["link_revoked"]:
			row["secure_link"] = get_url(f"/client-document/{token}")
		else:
			row["secure_link"] = ""

	return rows


# ---------------------------------------------------------------------------
# Guest side: the /client-document/<token> secure portal link
# ---------------------------------------------------------------------------

def _get_share_by_token(token):
	if not token:
		frappe.throw(_("This link is invalid."), frappe.DoesNotExistError)

	name = frappe.db.get_value(SHARE_DOCTYPE, {"access_token": token}, "name")
	if not name:
		frappe.throw(_("This link is invalid."), frappe.DoesNotExistError)

	return frappe.get_doc(SHARE_DOCTYPE, name)


def _ensure_link_usable(share):
	if share.link_revoked or share.status == "Revoked":
		frappe.throw(_("This link has been revoked."), frappe.PermissionError)

	if share.link_expires_on and share.link_expires_on < now_datetime():
		frappe.throw(_("This link has expired."), frappe.PermissionError)


def _record_access(share):
	if not share.viewed_on:
		share.viewed_on = now_datetime()

	if share.status == "Sent":
		share.status = "Viewed"

	share.access_count = (share.access_count or 0) + 1
	share.last_accessed_on = now_datetime()
	share.save(ignore_permissions=True)
	frappe.db.commit()


def get_shared_document_context(token):
	"""Used by www/client_document/index.py's get_context() - not
	whitelisted, this only ever runs server-side while rendering the page."""

	share = _get_share_by_token(token)
	_ensure_link_usable(share)
	_record_access(share)

	doc = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, share.practice_document)

	return {
		"token": token,
		"recipient_name": share.recipient_name,
		"document_title": doc.document_title,
		"document_code": doc.document_code,
		"version": doc.version,
		"summary": doc.summary,
		"sharing_instructions": doc.sharing_instructions,
		"client_action_required": share.client_action_required or "None",
		"has_file": bool(doc.attached_file),
		"status": share.status,
		"client_acknowledged": share.client_acknowledged,
		"client_response_on": share.client_response_on,
	}


@frappe.whitelist(allow_guest=True)
def submit_client_response(token, action, typed_name=None, signature=None):
	share = _get_share_by_token(token)
	_ensure_link_usable(share)

	action = (action or "").strip()

	if action == "acknowledge":
		share.client_acknowledged = 1
	elif action == "sign":
		typed_name = (typed_name or "").strip()
		if not typed_name or not signature:
			frappe.throw(_("Please type your name and provide a signature."))
		share.client_typed_name = typed_name
		share.client_signature = signature
		share.client_acknowledged = 1
	else:
		frappe.throw(_("Unknown action."))

	share.client_response_on = now_datetime()
	share.status = "Completed"
	share.completed_on = now_datetime()
	share.save(ignore_permissions=True)

	_generate_completion_record_pdf(share)

	frappe.db.commit()

	return {"status": share.status}


@frappe.whitelist(allow_guest=True)
def download_shared_document(token):
	share = _get_share_by_token(token)
	_ensure_link_usable(share)

	doc = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, share.practice_document)
	if not doc.attached_file:
		frappe.throw(_("No file is attached to this document."))

	_record_access(share)

	from frappe.utils.file_manager import get_file

	fname, fcontent = get_file(doc.attached_file)

	frappe.local.response.filename = fname
	frappe.local.response.filecontent = fcontent
	frappe.local.response.type = "download"


def _generate_completion_record_pdf(share):
	from frappe.utils.pdf import get_pdf

	doc = frappe.get_doc(PRACTICE_DOCUMENT_DOCTYPE, share.practice_document)

	html = f"""
		<h2>Completion Record</h2>
		<p><strong>Document:</strong> {escape_html(doc.document_title)}
			({escape_html(doc.document_code or "")} v{escape_html(doc.version or "")})</p>
		<p><strong>Recipient:</strong> {escape_html(share.recipient_name or "")} ({escape_html(share.recipient_type or "")})</p>
		<p><strong>Shared On:</strong> {share.shared_on or ""}</p>
		<p><strong>Viewed On:</strong> {share.viewed_on or ""}</p>
		<p><strong>Acknowledged:</strong> {"Yes" if share.client_acknowledged else "No"}</p>
		<p><strong>Typed Name:</strong> {escape_html(share.client_typed_name or "")}</p>
		<p><strong>Completed On:</strong> {share.client_response_on or ""}</p>
	"""

	if share.client_signature:
		html += f'<p><strong>Signature:</strong></p><img src="{share.client_signature}" style="max-width:300px;" />'

	pdf_content = get_pdf(html)

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"completion-record-{share.name}.pdf",
			"attached_to_doctype": share.doctype,
			"attached_to_name": share.name,
			"content": pdf_content,
			"is_private": 1,
		}
	)
	file_doc.save(ignore_permissions=True)

	frappe.db.set_value(share.doctype, share.name, "completion_record_pdf", file_doc.file_url)

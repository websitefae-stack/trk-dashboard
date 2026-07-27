import frappe
from frappe.model.document import Document
from frappe.utils import add_days, now_datetime

LINK_VALID_DAYS = 90


class ClientDocumentShare(Document):
	def before_insert(self):
		if not self.shared_by:
			self.shared_by = frappe.session.user

		if not self.shared_on:
			self.shared_on = now_datetime()

		if not self.status:
			self.status = "Prepared"

		if self.delivery_method == "Secure Portal Link" and not self.access_token:
			self.access_token = frappe.generate_hash(length=48)
			self.link_expires_on = add_days(now_datetime(), LINK_VALID_DAYS)

	def before_save(self):
		"""
		The original recipient a share was sent to can never be changed once
		it exists - a new Client Document Share is created instead (see the
		module docstring in api/shared/client_document_share.py). This is a
		last line of defence against a stray Desk edit doing it directly.
		"""
		if self.is_new():
			return

		previous = frappe.db.get_value(
			self.doctype,
			self.name,
			["recipient_contact", "recipient_email", "client"],
			as_dict=True,
		)

		if not previous:
			return

		if (
			previous.recipient_contact != self.recipient_contact
			or previous.recipient_email != self.recipient_email
			or previous.client != self.client
		):
			frappe.throw(
				"The recipient of a Client Document Share cannot be changed once it has "
				"been created. Revoke this share and create a new one instead."
			)

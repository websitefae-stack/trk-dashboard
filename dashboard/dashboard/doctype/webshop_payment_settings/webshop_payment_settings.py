import frappe
from frappe.model.document import Document


class WebshopPaymentSettings(Document):
	pass


def get_settings():
	return frappe.get_single("Webshop Payment Settings")

import frappe
from frappe.model.document import Document


class WebshopShippingSettings(Document):
	pass


def get_shipping_settings():
	return frappe.get_single("Webshop Shipping Settings")

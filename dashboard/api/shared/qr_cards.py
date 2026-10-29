"""
Saved logos ("QR Card Template") used by the franchisor dashboard's "QR
Codes" tool (public/js/shared/qr_cards.js) to compose a branded,
downloadable QR card - logo, a title, a QR code, and the destination URL,
in the style of the printed cards already used for things like "Get The
Brochure". The actual QR code and card image are both generated entirely
in the browser (the vendored qrcodejs library plus a <canvas>) - this
module only manages the reusable logo/corner-graphic assets so they don't
need re-uploading every time a new card is made.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in

DOCTYPE = "QR Card Template"


@frappe.whitelist()
def get_qr_card_templates():
	ensure_logged_in()

	return frappe.get_all(
		DOCTYPE,
		fields=["name", "template_name", "logo", "corner_graphic", "accent_color"],
		order_by="template_name asc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def create_qr_card_template(template_name=None, logo=None, corner_graphic=None, accent_color=None):
	ensure_logged_in()

	template_name = (template_name or "").strip()
	if not template_name:
		frappe.throw(_("Please enter a name for this logo."))

	if not logo:
		frappe.throw(_("Please upload a logo."))

	doc = frappe.get_doc({
		"doctype": DOCTYPE,
		"template_name": template_name,
		"logo": logo,
		"corner_graphic": corner_graphic or "",
		"accent_color": (accent_color or "").strip() or "#0D5C63",
	})
	doc.insert(ignore_permissions=True)

	return {"name": doc.name}


@frappe.whitelist()
def delete_qr_card_template(name=None):
	ensure_logged_in()

	name = (name or "").strip()
	if not name or not frappe.db.exists(DOCTYPE, name):
		frappe.throw(_("Logo not found."))

	frappe.delete_doc(DOCTYPE, name, ignore_permissions=True)

	return {"ok": 1}

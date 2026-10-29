"""
Backs the franchisor dashboard's "QR Codes" tool
(public/js/shared/qr_cards.js), which composes a branded, downloadable QR
card - logo, a title, a QR code, and the destination URL, in the style of
the printed cards already used for things like "Get The Brochure". Both
the QR code and the finished card image are generated entirely in the
browser (the vendored qrcodejs library plus a <canvas>) - this module
handles the two things that need to persist on the server:

- QR Card Template: a reusable logo (and optional corner graphic), saved
  once per brand so it's picked from a dropdown rather than re-uploaded
  for every card.
- QR Card: a previously-generated card's finished PNG (already uploaded
  by the browser via the core upload_file endpoint before this is
  called), saved so it can be re-downloaded later without regenerating -
  upserted by title, so re-generating a card with the same title updates
  the saved one in place instead of piling up duplicates.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in

TEMPLATE_DOCTYPE = "QR Card Template"
CARD_DOCTYPE = "QR Card"


@frappe.whitelist()
def get_qr_card_templates():
	ensure_logged_in()

	return frappe.get_all(
		TEMPLATE_DOCTYPE,
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
		"doctype": TEMPLATE_DOCTYPE,
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
	if not name or not frappe.db.exists(TEMPLATE_DOCTYPE, name):
		frappe.throw(_("Logo not found."))

	frappe.delete_doc(TEMPLATE_DOCTYPE, name, ignore_permissions=True)

	return {"ok": 1}


@frappe.whitelist()
def get_qr_cards():
	ensure_logged_in()

	return frappe.get_all(
		CARD_DOCTYPE,
		fields=["name", "title", "url", "qr_card_template", "image", "modified"],
		order_by="modified desc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def save_qr_card(title=None, url=None, image=None, qr_card_template=None):
	"""
	image is a file_url the browser already uploaded (via the core
	upload_file endpoint) for the finished, composed card PNG - this just
	records it. Upserts by title: generating a card again with the same
	title (the normal "I need another one of these" case) replaces the
	saved image/url/logo rather than leaving the old one sitting around
	as a separate, now-stale duplicate.
	"""
	ensure_logged_in()

	title = (title or "").strip()
	url = (url or "").strip()

	if not title:
		frappe.throw(_("Please enter a title."))
	if not url:
		frappe.throw(_("Please enter a link."))
	if not image:
		frappe.throw(_("Missing the generated card image."))

	existing_name = frappe.db.exists(CARD_DOCTYPE, {"title": title})

	if existing_name:
		doc = frappe.get_doc(CARD_DOCTYPE, existing_name)
		doc.url = url
		doc.image = image
		doc.qr_card_template = qr_card_template or ""
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({
			"doctype": CARD_DOCTYPE,
			"title": title,
			"url": url,
			"image": image,
			"qr_card_template": qr_card_template or "",
		})
		doc.insert(ignore_permissions=True)

	return {"name": doc.name}


@frappe.whitelist()
def delete_qr_card(name=None):
	ensure_logged_in()

	name = (name or "").strip()
	if not name or not frappe.db.exists(CARD_DOCTYPE, name):
		frappe.throw(_("Saved card not found."))

	frappe.delete_doc(CARD_DOCTYPE, name, ignore_permissions=True)

	return {"ok": 1}

"""
Capturing client testimonials (text, a photo, or a video) and attributing
each one to the coach who received it and the brand(s) it's for - a
single place for these instead of wherever they currently get collected.

A coach can only ever add/edit a testimonial under their own name (never
someone else's) and can only tick a brand they actually operate - see
_clean_brand_values(). The franchisor can add/edit/delete a
testimonial for any coach, and see every one. Deleting is franchisor-
only; a coach who's submitted one by mistake asks the office to remove
it rather than being able to make it disappear themselves.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import (
	ensure_logged_in,
	ensure_office_user,
	is_office_user,
	get_current_coach_name,
)
from dashboard.api.shared.coach_view_mode import get_coach_view_mode

DOCTYPE = "Coach Testimonial"
COACH_DOCTYPE = "Coach"

# doctype fieldname -> the Coach Brand Access value it corresponds to -
# same mapping/convention as practice_documents.PRACTICE_DOCUMENT_BRAND_
# FIELDS, just without the Franchise option (testimonials are always for
# one of the four client-facing brands).
BRAND_FIELDS = {
	"brand_access_kid": "Kid",
	"brand_access_teen": "Teen",
	"brand_access_people": "People",
	"brand_access_school": "School",
}

LIST_FIELDS = [
	"name", "coach", "testimonial_date", "testimonial_type", "client_name", "is_anonymous",
	"testimonial_text", "testimonial_file",
	"brand_access_kid", "brand_access_teen", "brand_access_people", "brand_access_school", "for_books",
]


def _get_coach_brands(coach_name):
	"""
	Mirrors webshop_purchase._get_coach_brands() - a coach with NO Coach
	Brand Access rows at all is treated as unrestricted (every brand
	available to tick), not as "access to nothing", since that child
	table has historically been left empty for plenty of real, active
	coaches. Only an EXPLICIT set of rows actually narrows the options.
	"""
	if not coach_name or not frappe.db.exists("DocType", "Coach Brand Access"):
		return set()

	rows = frappe.get_all(
		"Coach Brand Access",
		filters={"parent": coach_name, "parenttype": "Coach"},
		pluck="brand_access",
	)

	return {row for row in rows if row}


@frappe.whitelist()
def get_coach_options_for_testimonials():
	"""
	Every Coach, for the franchisor's own coach picker on this page -
	deliberately NOT coaches.get_coaches(), which excludes the logged-in
	user's own Coach record (built for the Coaches list page, where
	Ashley shouldn't see herself as a row there). Ashley is also a Coach
	record, so that same exclusion was hiding her from this picker -
	she's exactly the kind of person who'd receive a testimonial too.
	"""
	ensure_office_user()

	return frappe.get_all(
		COACH_DOCTYPE,
		fields=["name", "coach_name"],
		order_by="coach_name asc",
		limit_page_length=5000,
		ignore_permissions=True,
	)


@frappe.whitelist()
def get_coach_brand_options(coach=None):
	"""
	Which of the four brand checkboxes should be available for a given
	coach - every one of BRAND_FIELDS.values() if that coach has no
	Coach Brand Access rows (unrestricted - see _get_coach_brands), or
	only the ones actually in their Brand Access otherwise.
	"""
	ensure_logged_in()

	coach = (coach or "").strip()
	if not coach or not frappe.db.exists(COACH_DOCTYPE, coach):
		frappe.throw(_("Coach not found."))

	coach_brands = _get_coach_brands(coach)

	if not coach_brands:
		return list(BRAND_FIELDS.values())

	return [value for value in BRAND_FIELDS.values() if value in coach_brands]


def _clean_brand_values(doc_values, coach):
	"""
	Drops any ticked brand the coach isn't actually allowed - never
	trusts the browser's own checkbox-hiding to be the only gate, since
	this is a server call a coach could otherwise hit directly with any
	brand ticked regardless of what the form showed them.
	"""
	allowed = set(get_coach_brand_options(coach))

	for fieldname, brand_value in BRAND_FIELDS.items():
		if brand_value not in allowed:
			doc_values[fieldname] = 0

	return doc_values


@frappe.whitelist()
def get_my_coach_brand_options():
	ensure_logged_in()
	return get_coach_brand_options(get_current_coach_name())


@frappe.whitelist()
def get_my_testimonials(view_as=None, viewer=None):
	"""
	view_as/viewer mirror practice_documents._resolve_effective_user's own
	read-only "View as Coach" support - a franchisor viewing a specific
	coach's dashboard sees THAT coach's testimonials here, not their own
	(empty) list. coach_db/testimonials/index.html never shows the add/
	edit form while in view mode, so this is read-only in practice too.
	"""
	ensure_logged_in()

	view_as = (view_as or "").strip()
	if view_as:
		view_mode = get_coach_view_mode(scope=viewer, coach_name=view_as)
		if not view_mode.get("is_view_mode"):
			frappe.throw(_("You do not have permission to view this coach."), frappe.PermissionError)
		coach = view_mode.get("view_coach_name")
	else:
		coach = get_current_coach_name()

	return frappe.get_all(
		DOCTYPE,
		filters={"coach": coach},
		fields=LIST_FIELDS,
		order_by="testimonial_date desc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def get_testimonial_filter_default():
	"""
	The franchisor's own Coach name, if the logged-in office/Ashley login
	is also a Coach (Ashley is, which is exactly why she was previously
	missing from the picker - see get_coach_options_for_testimonials).
	The franchisor Testimonials page's filter defaults to this (her own
	testimonials first, same as a coach would see), falling back to "all
	coaches" for an office login that isn't itself a Coach.
	"""
	ensure_office_user()
	return get_current_coach_name(optional=True) or ""


@frappe.whitelist()
def get_all_testimonials(coach=None):
	"""
	coach="" (or omitted) returns every coach's testimonials - the
	Testimonials page itself never calls it that way by default (see
	get_testimonial_filter_default), but a franchisor can explicitly pick
	"All Coaches" in the filter to get this.
	"""
	ensure_office_user()

	filters = {}
	coach = (coach or "").strip()
	if coach:
		filters["coach"] = coach

	return frappe.get_all(
		DOCTYPE,
		filters=filters,
		fields=LIST_FIELDS,
		order_by="testimonial_date desc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def get_testimonial_for_edit(name=None):
	ensure_logged_in()

	name = (name or "").strip()
	if not name or not frappe.db.exists(DOCTYPE, name):
		frappe.throw(_("Testimonial not found."))

	doc = frappe.get_doc(DOCTYPE, name)

	if not is_office_user() and doc.coach != get_current_coach_name():
		frappe.throw(_("You do not have permission to access this testimonial."), frappe.PermissionError)

	return doc.as_dict()


@frappe.whitelist()
def save_testimonial(
	name=None,
	coach=None,
	testimonial_date=None,
	testimonial_type=None,
	client_name=None,
	is_anonymous=None,
	testimonial_text=None,
	testimonial_file=None,
	brand_access_kid=None,
	brand_access_teen=None,
	brand_access_people=None,
	brand_access_school=None,
	for_books=None,
):
	ensure_logged_in()

	office = is_office_user()

	if office:
		coach = (coach or "").strip()
		if not coach or not frappe.db.exists(COACH_DOCTYPE, coach):
			frappe.throw(_("Please choose a coach."))
	else:
		# A coach can only ever submit under their own name, regardless
		# of what this call is sent - never trusts the browser.
		coach = get_current_coach_name()

	testimonial_type = testimonial_type if testimonial_type in ("Text", "Photo", "Video") else "Text"

	name = (name or "").strip()
	existing_doc = None

	if name:
		if not frappe.db.exists(DOCTYPE, name):
			frappe.throw(_("Testimonial not found."))
		existing_doc = frappe.get_doc(DOCTYPE, name)
		if not office and existing_doc.coach != coach:
			frappe.throw(_("You do not have permission to edit this testimonial."), frappe.PermissionError)

	if testimonial_type == "Text" and not (testimonial_text or "").strip():
		frappe.throw(_("Please enter the testimonial text."))

	# A new file is only required outright when there isn't one already -
	# editing an existing photo/video testimonial without choosing a new
	# file keeps whatever's currently saved (see testimonial_file below),
	# rather than forcing a re-upload on every unrelated edit.
	existing_file = existing_doc.testimonial_file if existing_doc else ""
	if testimonial_type != "Text" and not testimonial_file and not existing_file:
		frappe.throw(_("Please upload a {0} file.").format(testimonial_type.lower()))

	values = _clean_brand_values({
		"brand_access_kid": 1 if int(brand_access_kid or 0) else 0,
		"brand_access_teen": 1 if int(brand_access_teen or 0) else 0,
		"brand_access_people": 1 if int(brand_access_people or 0) else 0,
		"brand_access_school": 1 if int(brand_access_school or 0) else 0,
	}, coach)

	values.update({
		"coach": coach,
		"testimonial_date": testimonial_date or frappe.utils.nowdate(),
		"testimonial_type": testimonial_type,
		# Not brand-gated - every coach can tick this regardless of which
		# brand(s) they operate, unlike the four checkboxes above.
		"for_books": 1 if int(for_books or 0) else 0,
		"client_name": "" if int(is_anonymous or 0) else (client_name or "").strip(),
		"is_anonymous": 1 if int(is_anonymous or 0) else 0,
		"testimonial_text": testimonial_text if testimonial_type == "Text" else "",
		"testimonial_file": (testimonial_file or existing_file) if testimonial_type != "Text" else "",
	})

	if existing_doc:
		existing_doc.update(values)
		existing_doc.save(ignore_permissions=True)
		doc = existing_doc
	else:
		doc = frappe.get_doc({"doctype": DOCTYPE, "created_by_user": frappe.session.user, **values})
		doc.insert(ignore_permissions=True)

	return {"name": doc.name}


@frappe.whitelist()
def delete_testimonial(name=None):
	ensure_office_user()

	name = (name or "").strip()
	if not name or not frappe.db.exists(DOCTYPE, name):
		frappe.throw(_("Testimonial not found."))

	frappe.delete_doc(DOCTYPE, name, ignore_permissions=True)

	return {"ok": 1}

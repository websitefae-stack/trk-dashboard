"""
School feedback on a safeguarding letter: "mention in the letter that
she holds relevant qualifications (and detail of what they are)... If
she is also a member of a professional association that would also be
good to put on." - adds the fields behind that, self-reported by the
coach/session worker on their own profile. These are only ever the
*default* value a new letter request pre-fills from (see
safeguarding_letters.get_request_form_defaults) - the requester can
change either for that specific request if something's changed since
their profile was last updated, same as every other judgement-call
field on the request (dbs_wording_option, childrens_barred_list_check,
etc.), and Ashley's own existing review/approve-and-sign step is what
actually puts them on the letter, not a separate verified flag here.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

QUALIFICATION_FIELDS = [
	{
		"fieldname": "qualifications",
		"fieldtype": "Small Text",
		"label": "Qualifications Held",
		"description": "Relevant qualifications for this role - the default a new safeguarding letter request pre-fills from, editable per request.",
		"module": "Dashboard",
	},
	{
		"fieldname": "professional_association",
		"fieldtype": "Data",
		"label": "Professional Association / Membership",
		"description": "e.g. a professional body or register this person belongs to, and their membership number if relevant.",
		"insert_after": "qualifications",
		"module": "Dashboard",
	},
]


def execute():
	targets = {}

	if frappe.db.exists("DocType", "Coach"):
		coach_meta = frappe.get_meta("Coach")
		anchor = "skills_strenghts" if coach_meta.has_field("skills_strenghts") else None
		fields = [dict(f) for f in QUALIFICATION_FIELDS]
		if anchor:
			fields[0]["insert_after"] = anchor
		targets["Coach"] = fields

	if frappe.db.exists("DocType", "Session Worker"):
		sw_meta = frappe.get_meta("Session Worker")
		anchor = "interest" if sw_meta.has_field("interest") else None
		fields = [dict(f) for f in QUALIFICATION_FIELDS]
		if anchor:
			fields[0]["insert_after"] = anchor
		targets["Session Worker"] = fields

	if not targets:
		return

	create_custom_fields(targets, ignore_validate=True)
	frappe.db.commit()

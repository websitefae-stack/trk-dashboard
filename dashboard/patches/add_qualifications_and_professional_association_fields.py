"""
School feedback on a safeguarding letter: "mention in the letter that
she holds relevant qualifications (and detail of what they are) for
which you have also verified. If she is also a member of a
professional association that would also be good to put on." - adds
the fields behind that, self-reported by the coach/session worker on
their own profile, with a separate qualifications_verified flag only
the franchisor can set (see profile.set_qualifications_verified) -
the letter only ever includes qualifications/professional association
once that's ticked, never an unverified self-report on an official
document.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

QUALIFICATION_FIELDS = [
	{
		"fieldname": "qualifications",
		"fieldtype": "Small Text",
		"label": "Qualifications Held",
		"description": "Relevant qualifications for this role - shown on safeguarding assurance letters once verified below.",
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
	{
		"fieldname": "qualifications_verified",
		"fieldtype": "Check",
		"label": "Qualifications & Professional Association Verified",
		"description": "Franchisor-only - ticked once the qualifications/professional association above have actually been checked. Safeguarding letters never include either field until this is ticked.",
		"insert_after": "professional_association",
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

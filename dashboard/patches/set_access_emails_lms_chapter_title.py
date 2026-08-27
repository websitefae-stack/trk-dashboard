"""
Wires up the one LMS chapter title we have direct confirmation of (from
a screenshot of the actual LMS course editor sidebar): "Access your
emails with Chantelle Venter" - note lowercase "your", matching the LMS
chapter title exactly, not the onboarding step's own title ("Access Your
Emails..."). See _resolve_lms_chapter in api/shared/onboarding.py - the
match against Course Chapter.title has to be exact.

Every other LMS step's chapter title is left for HQ to fill in via the
franchisor Onboarding page's "Manage Step List" screen (copy-pasted
straight from the LMS course editor, not guessed here) - safer than this
patch guessing at titles it was never shown.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"

STEP_NAME = "Access Your Emails with Chantelle Venter"
LMS_CHAPTER_TITLE = "Access your emails with Chantelle Venter"


def execute():
	try:
		_set_lms_chapter_title()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "set_access_emails_lms_chapter_title failed")


def _set_lms_chapter_title():
	if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
		return

	step_name = frappe.db.get_value(ONBOARDING_STEP_DOCTYPE, {"step_name": STEP_NAME})
	if not step_name:
		return

	frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, step_name, "lms_chapter_title", LMS_CHAPTER_TITLE, update_modified=False)

	if frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
		frappe.db.set_value(
			COACH_ONBOARDING_STEP_DOCTYPE,
			{"onboarding_step": step_name},
			"lms_chapter_title",
			LMS_CHAPTER_TITLE,
			update_modified=False,
		)

	frappe.db.commit()

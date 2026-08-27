"""
Coach Onboarding Master Step's LMS Chapter used to be a free-text
"LMS Chapter Title" field matched against Course Chapter.title, plus a
separate lms_course text field - both replaced with real Link fields
(lms_course -> LMS Course, lms_chapter -> Course Chapter) since matching
by typed/picked title text turned out unreliable in practice. This
migrates the one step that already had a title set (from
set_access_emails_lms_chapter_title.py) across to the new lms_chapter
Link value, so it isn't lost. lms_course's own stored value is already a
real LMS Course name from that same earlier patch, so it doesn't need
migrating - only the type declaration changed (Data -> Link), which
doesn't touch what's already stored.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"
COACH_ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Step"
LMS_COURSE_CHAPTER_DOCTYPE = "Course Chapter"

# The old free-text field is gone from both doctypes' JSON, but the
# underlying database column is still there (Frappe never auto-drops a
# column just because it left the schema) - read straight from SQL
# rather than through the ORM/get_all, which would reject a field the
# current doctype metadata no longer declares.
OLD_TITLE_COLUMN = "lms_chapter_title"


def execute():
	try:
		_migrate()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "migrate_lms_chapter_title_to_link failed")


def _migrate():
	if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
		return

	if OLD_TITLE_COLUMN not in frappe.db.get_table_columns(ONBOARDING_STEP_DOCTYPE):
		return

	rows = frappe.db.sql(
		"""
		SELECT name, `lms_chapter_title` AS chapter_title, `lms_course` AS course
		FROM `tabCoach Onboarding Master Step`
		WHERE `lms_chapter_title` IS NOT NULL AND `lms_chapter_title` != ''
		""",
		as_dict=True,
	)

	if not rows:
		return

	have_lms = frappe.db.exists("DocType", LMS_COURSE_CHAPTER_DOCTYPE)

	for row in rows:
		chapter_name = None
		if have_lms:
			filters = {"title": row.chapter_title}
			if row.course:
				filters["course"] = row.course
			chapter_name = frappe.db.get_value(LMS_COURSE_CHAPTER_DOCTYPE, filters)

		if not chapter_name:
			frappe.log_error(
				f"Step: {row.name}\nOld chapter title: {row.chapter_title}\nCourse: {row.course}",
				"LMS Chapter Title Migration - No Match",
			)
			continue

		frappe.db.set_value(ONBOARDING_STEP_DOCTYPE, row.name, "lms_chapter", chapter_name, update_modified=False)

		if frappe.db.exists("DocType", COACH_ONBOARDING_STEP_DOCTYPE):
			frappe.db.set_value(
				COACH_ONBOARDING_STEP_DOCTYPE,
				{"onboarding_step": row.name},
				"lms_chapter",
				chapter_name,
				update_modified=False,
			)

	frappe.db.commit()

"""
Before get_affiliate_commission_catalog() filtered the Products list down
to custom_store_enabled=1 items, it listed every non-disabled Item -
including a paid course's own backing Item (store_products._ensure_
course_item, item code "LMS-COURSE-<course name>", deliberately
custom_store_enabled=0 so it never shows in the general store grid - it
only exists so the course can be added to the same cart as physical
products). Ashley enabled an Affiliate Product Setting on one of those
backing items (confirmed live: "Primary Anxiety Toolkit" showed twice in
a coach's "Your Links" - once from the Course itself, once from its
backing Item), not realising it was the same course as the one she'd
already set a commission on directly.

That's always redundant, never a second real product: _record_affiliate_
commission_for_invoice already falls back from an item-level setting to
the Item's custom_unlocks_lms_course -> Course-level setting whenever no
direct item setting exists, specifically so a course bought via its
backing Item (the /buy?item=LMS-COURSE-... link) still earns commission
off the Course-level setting alone. So disabling the Item-level one here
loses no commission-earning ability - it just stops it being counted (and
linked) twice.
"""

import frappe

from dashboard.api.shared.affiliate import AFFILIATE_SETTING_DOCTYPE


def execute():
	if not frappe.db.exists("DocType", AFFILIATE_SETTING_DOCTYPE):
		return

	if not frappe.get_meta("Item").has_field("custom_unlocks_lms_course"):
		return

	backing_items = frappe.get_all(
		"Item",
		filters={"custom_unlocks_lms_course": ["is", "set"]},
		pluck="name",
	)

	if not backing_items:
		return

	settings = frappe.get_all(
		AFFILIATE_SETTING_DOCTYPE,
		filters={"item": ["in", backing_items], "enabled": 1},
		pluck="name",
	)

	for setting_name in settings:
		frappe.db.set_value(AFFILIATE_SETTING_DOCTYPE, setting_name, "enabled", 0)

	if settings:
		frappe.db.commit()

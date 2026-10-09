"""
Replaces the discontinued "Soft shell jacket or Fleece or Body Warmer"
starter-kit clothing option with "Hoodie or Sweatshirt" on the already-
live Franchise Brochure content - that range's been dropped. Plain
string replace on whatever's actually stored right now (rather than
re-seeding the whole content again), same reasoning as fix_franchise_
brochure_content_links.py - doesn't clobber any other edit made in
Desk since seed_franchise_brochure_content.py ran.
"""

import frappe

DOCTYPE_NAME = "Franchise Brochure"

OLD_TEXT = "<p>Soft shell jacket or Fleece or Body Warmer</p>"
NEW_TEXT = "<p>Hoodie or Sweatshirt</p>"


def execute():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    content = frappe.db.get_single_value(DOCTYPE_NAME, "content") or ""
    if not content or OLD_TEXT not in content:
        return

    frappe.db.set_value(DOCTYPE_NAME, DOCTYPE_NAME, "content", content.replace(OLD_TEXT, NEW_TEXT))
    frappe.db.commit()

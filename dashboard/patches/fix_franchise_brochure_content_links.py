"""
The brochure content's "View Investment"/"See What's Included" buttons
used bare same-page anchors (href="#investment", href="#what-is-
included") - fine on the live /franchise-brochure page (which has a
matching id="investment" section in the same content), meaningless in
a downloaded PDF, which isn't "on" any page at all. Points them at the
real, permanently-public marketing page those sections were copied
from instead (/trh-franchise#investment etc) - works from anywhere,
PDF included, no token required.

Does a plain string replace on whatever's actually stored right now
(rather than re-seeding the whole content again), so it doesn't
clobber any other edit made in Desk since seed_franchise_brochure_
content.py ran.
"""

import frappe

DOCTYPE_NAME = "Franchise Brochure"
PUBLIC_SITE_URL = "https://theresilienthub.co.uk"

REPLACEMENTS = [
    ('href="#investment"', f'href="{PUBLIC_SITE_URL}/trh-franchise#investment"'),
    ('href="#what-is-included"', f'href="{PUBLIC_SITE_URL}/trh-franchise#what-is-included"'),
]


def execute():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    content = frappe.db.get_single_value(DOCTYPE_NAME, "content") or ""
    if not content:
        return

    updated = content
    for old, new in REPLACEMENTS:
        updated = updated.replace(old, new)

    if updated == content:
        return

    frappe.db.set_value(DOCTYPE_NAME, DOCTYPE_NAME, "content", updated)
    frappe.db.commit()

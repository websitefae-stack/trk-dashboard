"""
Adds a dedicated "Hero Image" upload field onto Frappe Blog's own "Blog
Post" doctype - blog only ships "Meta Image" (an SEO/social-share og:image
that never actually renders on the post page itself, tucked away under a
Meta Tags section), so there was nowhere obvious to upload an image meant
to actually show at the top of a post. Kept separate from Meta Image
deliberately, since that field also drives a real validation rule
("A featured post must have a cover image") this shouldn't get tangled
up in.

See resilient_domains's blog_branding.py for where this actually gets
rendered.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

BLOG_POST_FIELDS = [
    {
        "fieldname": "custom_hero_image",
        "fieldtype": "Attach Image",
        "label": "Hero Image",
        "description": "Shown at the top of the post on the public site.",
        "insert_after": "blog_intro",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Blog Post"):
        return

    create_custom_fields({"Blog Post": BLOG_POST_FIELDS}, ignore_validate=True)
    frappe.db.commit()

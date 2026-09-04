"""
Blog Post extras that aren't worth a whole app - see
add_blog_post_hero_image_field.py for the custom field itself.
"""

import frappe


def ensure_hero_image_public(doc, method=None):
    """
    Desk's own Attach Image uploader lets Private stay ticked - harmless
    for most files, but this one is rendered directly on the public
    resilient_domains blog post page (a different, unauthenticated site),
    same problem the coach profile photo had (see
    make_existing_coach_photos_public.py) - a private File 404s/hangs
    there since it needs a logged-in Frappe session to serve. Flips it
    public automatically rather than relying on Ashley remembering to
    untick Private every time she uploads one.
    """
    if not doc.get("custom_hero_image"):
        return

    file_name = frappe.db.get_value("File", {"file_url": doc.custom_hero_image}, "name")

    if not file_name:
        return

    file_doc = frappe.get_doc("File", file_name)

    if not file_doc.is_private:
        return

    file_doc.is_private = 0
    file_doc.save(ignore_permissions=True)

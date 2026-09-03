"""
The coach profile photo was uploaded through _save_optional_file() with
is_private hardcoded to 1 (same as the legal documents it also handles) -
fixed going forward by passing is_private=0 for the photo field specifically
(see profile.py), since it's rendered on the public resilient_domains
coach-profile pages, an unauthenticated site on a different domain, where a
private File 404s/hangs since it requires a logged-in Frappe session to
serve. This backfills every Coach's already-uploaded photo (and any linked
User's user_image, set from the same upload) so photos already on file
before that fix start rendering publicly too, without anyone re-uploading.

Setting File.is_private = 0 and saving it is the supported way to flip an
existing file's privacy - the File controller moves the physical file
between the private/public folders and updates file_url itself.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Coach"):
        return

    try:
        _make_public("Coach", "photo")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "make_existing_coach_photos_public failed")


def _make_public(doctype, fieldname):
    rows = frappe.get_all(
        doctype,
        filters={fieldname: ["not in", ("", None)]},
        fields=["name", fieldname, "user", "coach_email"],
    )

    for row in rows:
        old_file_url = row.get(fieldname)

        file_name = frappe.db.get_value("File", {"file_url": old_file_url}, "name")

        if not file_name:
            continue

        try:
            file_doc = frappe.get_doc("File", file_name)

            if not file_doc.is_private:
                continue

            file_doc.is_private = 0
            file_doc.save(ignore_permissions=True)

            # File.save() above already moved photo/user_image on Coach
            # itself (it looks up which of Coach's own fields held the old
            # URL and rewrites that one) - but a linked User's user_image is
            # a separate copy of the same URL set by update_my_profile, on a
            # different doctype the File was never attached_to, so it never
            # gets found/rewritten by that lookup and is fixed here instead.
            linked_user = row.get("user") or row.get("coach_email")

            if linked_user and frappe.db.get_value("User", linked_user, "user_image") == old_file_url:
                frappe.db.set_value(
                    "User", linked_user, "user_image", file_doc.file_url, update_modified=False,
                )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Make Coach Photo Public Failed - {row.name}")

    frappe.db.commit()

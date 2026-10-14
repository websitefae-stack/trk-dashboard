"""
Tracking redirect for the "Links" page (dashboard.api.shared.form_
reports.get_form_links/_tracked_link_url) - every link/QR code shown
there points here first so an actual click/scan gets logged, then goes
on to its real destination. No login required by design: these are the
same already-guest-accessible pages (Web Forms, booking links, static
pages) the link would have gone to directly before.
"""

from urllib.parse import unquote

import frappe


def get_context(context):
    # Never cache - every visit needs to run this and log its own click,
    # not serve back whatever happened to render (or not render, since
    # this always redirects) on an earlier hit.
    context.no_cache = 1

    target = unquote(frappe.form_dict.get("u") or "")

    if not target:
        frappe.local.flags.redirect_location = "/"
        raise frappe.Redirect

    try:
        frappe.get_doc({
            "doctype": "Dashboard Link Click",
            "link_title": unquote(frappe.form_dict.get("t") or ""),
            "target_url": target,
            "form_doctype": unquote(frappe.form_dict.get("d") or "") or None,
            "clicked_on": frappe.utils.now_datetime(),
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        # Never let a tracking failure block the actual redirect - a
        # missed click log is a far smaller problem than a dead link.
        frappe.log_error(frappe.get_traceback(), "Link Click Tracking Failed")

    frappe.local.flags.redirect_location = target
    raise frappe.Redirect

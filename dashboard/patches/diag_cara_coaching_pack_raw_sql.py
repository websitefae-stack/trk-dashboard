"""
TEMPORARY diagnostic only - follow-up to diag_cara_coaching_pack_visibility.
That patch proved a real contradiction: COA012's own Item Defaults row
for Cara's company shows Show on Site ticked when read via the Item
document, but the exact same company+custom_show_on_site=1 query the
coach-profile page actually runs does not return COA012 at all. Both
reads hit the same tabItem Default table, so something at the raw row
level must differ from what the document view shows. This dumps every
literal column of every tabItem Default row attached to COA012, with
no document-layer interpretation in between, to find it. Read-only,
safe to delete once the cause is found.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        """
        select name, idx, parent, parenttype, parentfield, company,
               custom_show_on_site, default_warehouse, default_price_list
        from `tabItem Default`
        where parent = %s
        order by idx
        """,
        ("COA012",),
        as_dict=True,
    )

    lines = [f"Raw tabItem Default rows where parent='COA012' ({len(rows)} rows):"]
    for row in rows:
        lines.append(repr(row))

    coach_company = frappe.db.get_value("Coach", "Cara Callaghan", "company")
    lines.append(f"\ncoach.company raw from frappe.db.get_value = {coach_company!r}")

    direct_match = frappe.db.sql(
        """
        select name, idx, parent, company, custom_show_on_site
        from `tabItem Default`
        where parent = %s and company = %s
        """,
        ("COA012", coach_company),
        as_dict=True,
    )
    lines.append(f"\nDirect SQL match on parent=COA012 AND company={coach_company!r}: {direct_match}")

    like_match = frappe.db.sql(
        """
        select name, idx, parent, company, custom_show_on_site
        from `tabItem Default`
        where parent = %s and company like %s
        """,
        ("COA012", f"%{coach_company}%"),
        as_dict=True,
    )
    lines.append(f"\nLIKE match (catches hidden whitespace/char differences): {like_match}")

    frappe.log_error("\n".join(lines), "Cara 12 Session Raw SQL Diagnostic")

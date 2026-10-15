"""
TEMPORARY diagnostic only - logs the exact values the trh/trk coach-
profile pages' get_offered_services() checks for Cara Callaghan and
"12 Session Coaching Pack" (COA012). Every piece of data shown in the
Service Access grid and the Item's own Item Defaults row says this
should already be showing on her public page, and it isn't - this is a
one-time, read-only dump to the Error Log to see the real values the
database actually holds, instead of guessing further from screenshots.
Safe to delete once the cause is found; makes no changes.
"""

import frappe


def execute():
    lines = []

    if not frappe.db.exists("Coach", "Cara Callaghan"):
        frappe.log_error("DIAG: no Coach named 'Cara Callaghan' found", "Cara 12 Session Diagnostic")
        return

    coach = frappe.get_doc("Coach", "Cara Callaghan")
    lines.append(f"coach.name = {coach.name!r}")
    lines.append(f"coach.company = {coach.company!r}")

    if not frappe.db.exists("Item", "COA012"):
        lines.append("Item COA012 does not exist on this site")
        frappe.log_error("\n".join(lines), "Cara 12 Session Diagnostic")
        return

    item = frappe.get_doc("Item", "COA012")
    lines.append(f"item.item_name = {item.item_name!r}")
    lines.append(f"item.disabled = {item.disabled!r}")
    lines.append(f"item.item_group = {item.item_group!r}")
    lines.append(f"item.variant_of = {item.variant_of!r}")
    lines.append(f"item.custom_brand_hub = {item.get('custom_brand_hub')!r}")
    lines.append(f"item.custom_brand_kid = {item.get('custom_brand_kid')!r}")
    lines.append(f"item.custom_store_enabled = {item.get('custom_store_enabled')!r}")

    lines.append("--- item_defaults rows on COA012 ---")
    for row in item.get("item_defaults") or []:
        lines.append(
            f"row company={row.company!r} show_on_site={row.get('custom_show_on_site')!r} "
            f"(matches coach.company: {row.company == coach.company})"
        )

    shown = frappe.get_all(
        "Item Default",
        filters={"company": coach.company, "custom_show_on_site": 1},
        pluck="parent",
        limit_page_length=500,
    )
    lines.append(f"shown_item_codes for coach.company via frappe.get_all = {shown}")
    lines.append(f"COA012 in shown_item_codes = {'COA012' in shown}")

    if shown:
        items = frappe.get_all(
            "Item",
            filters={
                "name": ["in", shown],
                "custom_brand_hub": 1,
                "disabled": 0,
                "item_group": ["!=", "Courses"],
            },
            fields=["name", "item_name"],
        )
        lines.append(f"Items passing the Hub-page filter = {items}")

    frappe.log_error("\n".join(lines), "Cara 12 Session Diagnostic")

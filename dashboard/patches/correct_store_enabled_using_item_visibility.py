"""
Corrects backfill_store_enabled_for_merch_items.py, which guessed
"not Services/Courses, not workshop/coaching-shaped by name" to find
merch missing custom_store_enabled - too loose a rule, since it also
caught real services whose Item Group isn't workshop/coaching-shaped
either (e.g. "CPD Training", Item Group "Staff CPD").

custom_item_visibility is a far more reliable signal: it starts blank
on every item and is only ever written by the Store's own Add/Edit
Product flow (see add_item_visibility_and_coach_price_list.py's own
docstring - "Blank (every existing item, before this patch) is
treated as Everyone... no backfill needed"), so a genuinely non-blank
value means the item was deliberately configured as a Store product
at some point. Used two ways here:

- A non-blank custom_item_visibility is positive proof of a Store
  product - setting custom_store_enabled=1 off the back of it alone
  (regardless of Item Group) should also catch anything the looser
  group-name guess missed entirely.
- Anything the previous patch set custom_store_enabled=1 on that
  still has a blank custom_item_visibility was never actually
  configured as a Store product through that flow - reverted back to
  0 here, since that's exactly the shape of the CPD Training-style
  false positive.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Item"):
        return

    item_meta = frappe.get_meta("Item")

    if not item_meta.has_field("custom_store_enabled") or not item_meta.has_field("custom_item_visibility"):
        return

    confirmed_store_items = frappe.get_all(
        "Item",
        filters={"custom_item_visibility": ["in", ["Everyone", "Coach Only"]], "custom_store_enabled": ["!=", 1]},
        pluck="name",
    )

    for name in confirmed_store_items:
        frappe.db.set_value("Item", name, "custom_store_enabled", 1, update_modified=False)

    false_positives = frappe.get_all(
        "Item",
        filters={
            "custom_store_enabled": 1,
            "custom_item_visibility": ["in", ["", None]],
        },
        pluck="name",
    )

    for name in false_positives:
        frappe.db.set_value("Item", name, "custom_store_enabled", 0, update_modified=False)

    frappe.db.commit()

    if confirmed_store_items or false_positives:
        frappe.log_error(
            "correct_store_enabled_using_item_visibility: set custom_store_enabled=1 on {0} confirmed "
            "Store item(s), reverted it to 0 on {1} false positive(s).\n\nConfirmed:\n{2}\n\nReverted:\n{3}".format(
                len(confirmed_store_items),
                len(false_positives),
                "\n".join(confirmed_store_items),
                "\n".join(false_positives),
            ),
            "Store Enabled Correction",
        )

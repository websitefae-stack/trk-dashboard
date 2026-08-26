"""
CRITICAL FIX: the custom doctype originally created for the Coach
Onboarding Journey feature was named "Onboarding Step" - which is also
the name of a doctype Frappe's own core framework ships (used for
ERPNext's built-in "Getting Started" setup guidance on its Selling,
Buying, Manufacturing, Accounts, Stock modules etc.). DocType names are
unique per site, so syncing a doctype JSON with that same name onto an
existing core doctype overwrote its field structure with this app's
custom fields (step_name, owner_type, stage, etc.) instead of Frappe's
own. That's why the live table ended up with far more rows than this
app ever seeded (real ERPNext onboarding content mixed in with this
app's own), and why some of that mixed-in content had no step_name -
those are the real ERPNext records, which never had a field by that
name to begin with.

This renames the doctype (table, all Link field references across the
whole site, everything) from "Onboarding Step" to
"Coach Onboarding Master Step" - a name that can't collide with
anything else. This is entirely non-destructive: frappe.rename_doc()
moves the existing table and all its data (this app's real ~36 steps
plus whatever ERPNext content is still mixed in) to the new name,
nothing is deleted.

Once the old "Onboarding Step" name is free again, Frappe's own
standard doctype-schema sync (which runs on every migrate, for every
installed app including the core frappe framework itself) will find no
existing record under that name and recreate Frappe's genuine core
doctype fresh from its own unmodified source - restoring the correct
schema automatically. Whether ERPNext's own onboarding *content*
(the actual step records, not just the schema) comes back automatically
depends on how ERPNext itself seeds that data; if it doesn't reappear
on its own, Frappe Cloud's automatic site backups (Site > Backups) are
the way to recover it from a point before this ever happened.
"""

import frappe

OLD_NAME = "Onboarding Step"
NEW_NAME = "Coach Onboarding Master Step"


def execute():
    if frappe.db.exists("DocType", NEW_NAME):
        return

    if not frappe.db.exists("DocType", OLD_NAME):
        return

    # Only touch it if this really is the hijacked version (has this
    # app's own step_name field) - never rename a doctype called
    # "Onboarding Step" that turns out to be a genuine, untouched core
    # one for some reason.
    if not frappe.get_meta(OLD_NAME).has_field("step_name"):
        return

    frappe.rename_doc("DocType", OLD_NAME, NEW_NAME, force=True)
    frappe.clear_cache(doctype=NEW_NAME)
    frappe.db.commit()

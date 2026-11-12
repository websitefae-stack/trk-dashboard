"""
Flips Applies To from "Coach" to "Both" on the exact set of existing
Coach Onboarding Master Step rows from Ashley's own onboarding list
("Email account created", "Your Logins hub set up", etc.) - her
explicit scope, re-pasted verbatim when asked to confirm "flip
everything" vs. "pick specific steps" (she picked specific - this
list). Not a blanket mirror of every Coach step.

Matched by step_name (case-insensitive partial match - the exact live
wording may differ slightly from how she typed it out) for everything
she named individually. "Stage 5 - Policies" and "Stage 8 - Get Client
Ready" were named as whole stages with no individual steps listed
under them, so every step under those two stages is flipped instead.

Goes through doc.save() rather than a direct frappe.db.set_value so
Coach Onboarding Master Step's own on_update hook
(onboarding.sync_master_step_active_state) fires exactly as it would
from a real Desk edit - backfilling the step onto every session worker
already mid-onboarding (Francesca Hammond's "1 of 1 steps done"
included), not just ones who start onboarding from now on.

Logs (not throws) when a name/stage match finds nothing, so a wording
mismatch surfaces for a follow-up fix instead of silently skipping it.
Safe to re-run - already-Both rows are left alone.
"""

import frappe

MASTER_STEP_DOCTYPE = "Coach Onboarding Master Step"

# (case-insensitive fragment matched against step_name)
STEP_NAME_FRAGMENTS = [
    "email account created",
    "your logins",
    "clothing sizes",
    "lms onboarding course",
    "access your emails with chantelle venter",
    "up your profile",  # catches "Set Up Your Profile" / "Setup Up Your Profile" either spelling
    "parents course",
    "operations manual",
    "photoshoot images",
    "email signature",
    "print materials",
]

# Whole stages Ashley named without listing individual steps under them.
STAGE_PREFIXES = [
    "Stage 5",
    "Stage 8",
]


def execute():
    if not frappe.db.exists("DocType", MASTER_STEP_DOCTYPE):
        return

    if not frappe.get_meta(MASTER_STEP_DOCTYPE).has_field("applies_to"):
        return

    names_to_flip = set()

    for fragment in STEP_NAME_FRAGMENTS:
        matches = frappe.get_all(
            MASTER_STEP_DOCTYPE,
            filters=[["step_name", "like", "%{0}%".format(fragment)]],
            pluck="name",
        )
        if not matches:
            frappe.log_error(
                "No Coach Onboarding Master Step matched step_name fragment: {0!r}".format(fragment),
                "Session Worker Onboarding List - Step Name Not Found",
            )
            continue
        names_to_flip.update(matches)

    for prefix in STAGE_PREFIXES:
        matches = frappe.get_all(
            MASTER_STEP_DOCTYPE,
            filters=[["stage", "like", "{0}%".format(prefix)]],
            pluck="name",
        )
        if not matches:
            frappe.log_error(
                "No Coach Onboarding Master Step found under stage prefix: {0!r}".format(prefix),
                "Session Worker Onboarding List - Stage Not Found",
            )
            continue
        names_to_flip.update(matches)

    for name in names_to_flip:
        try:
            doc = frappe.get_doc(MASTER_STEP_DOCTYPE, name)
            if doc.applies_to == "Coach":
                doc.applies_to = "Both"
                doc.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Session Worker Onboarding List - Flip Failed - {0}".format(name),
            )

    frappe.db.commit()

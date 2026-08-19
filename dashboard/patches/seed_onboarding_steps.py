"""
Seeds the agreed Coach Onboarding Journey step list (Stages 2-10 - Stage 1,
the pre-hire Franchise pipeline, isn't part of Coach Onboarding Step at
all, since it happens before a Coach record exists). Idempotent: skips any
step_name that already exists, so re-running this (or HQ having already
started editing the list in the Desk) never creates duplicates.

Every Stage 3+ step depends on "Training Day" being marked Done first -
the one dependency worth wiring up front, since it's the single real gate
in the whole journey (nothing meaningfully starts before the coach has
actually been trained). Everything else is ordered by stage/sort_order
alone; HQ can add finer-grained "Depends On" links later in the Desk if
particular steps need it.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Onboarding Step"

# (stage_sort_order, stage_label, [(sort_order, step_name, owner_type, where_it_happens, expected_result), ...])
STAGES = [
    (2, "Stage 2 - Get Ready", [
        (1, "Email account created", "HQ", "Manual / External (email provider)",
         "Coach has a working @resilientkid email."),
        (2, "\"Your Logins\" hub set up", "HQ", "Frappe",
         "One link (theresilienthub.co.uk) + one password gets the coach a page listing every login they "
         "have, plus how-to-access instructions for each."),
        (3, "Frappe Dashboard account created (view access only)", "HQ", "Frappe",
         "Coach can log in and look around/follow along, but can't act on real data yet - no clients exist "
         "for them yet."),
        (4, "Social media account created (setup only, not branded)", "HQ", "External (social platform)",
         "Account exists, ready to be branded once photos are back."),
    ]),
    (3, "Stage 3 - Training Day", [
        (1, "Training Day - curriculum, Resilient Kid Values, Resilient Kid Framework, Photoshoot",
         "HQ delivers / Coach attends", "In-Person",
         "Day completed and marked done - this is what unlocks every later stage."),
        (2, "Access Your Emails", "Coach", "LMS", "Module marked complete in LMS."),
        (3, "Branding Shots for Business", "Coach", "LMS", "Module marked complete in LMS."),
        (4, "Operations Manual", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (4, "Stage 4 - Get Business Ready", [
        (1, "HQ processes & delivers photoshoot images", "HQ", "Manual", "Branded photos delivered to the coach."),
        (2, "HQ finalises social media account with branding", "HQ", "External (social platform)",
         "Account fully branded, ready to post."),
        (3, "Email signature set up (with photo)", "HQ", "External (email client)", "Signature added and in use."),
    ]),
    (5, "Stage 5 - Get Visible", [
        (1, "Graphics / Canva Training", "Coach", "LMS", "Module marked complete in LMS."),
        (2, "Social Media Training - basics", "Coach", "LMS", "Module marked complete in LMS."),
        (3, "B-Roll Guide", "Coach", "LMS", "Module marked complete in LMS."),
        (4, "LinkedIn Training", "Coach", "LMS", "Module marked complete in LMS."),
        (5, "Mission-Led Content", "Coach", "LMS", "Module marked complete in LMS."),
        (6, "Talking About Your Business", "Coach", "LMS", "Module marked complete in LMS."),
        (7, "The Stories We Should Be Telling", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (6, "Stage 6 - Build Your Local Business", [
        (1, "Building a Networking Strategy", "Coach", "LMS", "Module marked complete in LMS."),
        (2, "Networking - the C.O.N.N.E.C.T. Method", "Coach", "LMS", "Module marked complete in LMS."),
        (3, "PR Training", "Coach", "LMS", "Module marked complete in LMS."),
        (4, "Confidence", "Coach", "LMS", "Module marked complete in LMS."),
        (5, "The Marketing Momentum Circle", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (7, "Stage 7 - Get Client Ready", [
        (1, "Onboarding and Offboarding Clients", "Coach", "LMS", "Module marked complete in LMS."),
        (2, "Safeguarding + essential policies", "Coach", "Frappe - Practice Documents",
         "Mandatory policies read/acknowledged/signed as required."),
        (3, "Frappe Dashboard practice (sandbox)", "Coach", "Frappe - coming soon (Tier 3)",
         "Coach can create a lead, send an intake email, have a client complete the form, convert to "
         "Client + Contact, raise an invoice, book an appointment, mark an invoice paid, and view reports "
         "and documents - all against sandbox data, with any triggered email going to the coach's own "
         "address rather than a fictional client."),
    ]),
    (8, "Stage 8 - Learn Your Systems", [
        (1, "Frappe Training", "Coach", "LMS", "Module marked complete in LMS."),
        (2, "Live Frappe follow-up session with Chantelle", "Coach", "In-Person / External",
         "Hands-on session completed, after the LMS module."),
        (3, "Accounting Training", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (9, "Stage 9 - Grow", [
        (1, "Business Coaching", "Coach", "LMS", "Module marked complete in LMS."),
        (2, "Manage ADHD", "Coach", "LMS", "Module marked complete in LMS."),
        (3, "How to WOW", "Coach", "LMS", "Module marked complete in LMS."),
        (4, "Fierce Principles", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (10, "Stage 10 - Launch", [
        (1, "Final checks", "HQ", "Manual", "HQ confirms everything required is actually complete."),
        (2, "Coaches Feedback", "Coach", "LMS", "Module marked complete in LMS."),
        (3, "Certification", "Coach", "LMS",
         "Certificate issued - only once everything above is actually complete."),
    ]),
]


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    training_day_name = frappe.db.get_value(
        ONBOARDING_STEP_DOCTYPE,
        {"step_name": "Training Day - curriculum, Resilient Kid Values, Resilient Kid Framework, Photoshoot"},
    )

    for stage_sort_order, stage_label, steps in STAGES:
        for sort_order, step_name, owner_type, where_it_happens, expected_result in steps:
            if frappe.db.exists(ONBOARDING_STEP_DOCTYPE, {"step_name": step_name}):
                continue

            depends_on = training_day_name if stage_sort_order > 3 else None

            doc = frappe.get_doc({
                "doctype": ONBOARDING_STEP_DOCTYPE,
                "step_name": step_name,
                "is_active": 1,
                "owner_type": owner_type,
                "stage": stage_label,
                "stage_sort_order": stage_sort_order,
                "sort_order": sort_order,
                "expected_result": expected_result,
                "where_it_happens": where_it_happens,
                "depends_on": depends_on,
            })
            doc.insert(ignore_permissions=True)

            if step_name == "Training Day - curriculum, Resilient Kid Values, Resilient Kid Framework, Photoshoot":
                training_day_name = doc.name

    frappe.db.commit()

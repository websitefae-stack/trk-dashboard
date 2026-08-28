"""
Seeds the agreed Coach Onboarding Journey step list (Stages 2-11 - Stage 1,
the pre-hire Franchise Lead pipeline, isn't part of Coach Onboarding Step at
all, since it happens before a Coach record exists - and is on hold for now,
not being built while no new franchisees are being taken on). Idempotent:
skips any step_name that already exists, so re-running this (or HQ having
already started editing the list in the Desk) never creates duplicates.

Every Stage 4+ step depends on "Training Day" being marked Done first -
the one dependency worth wiring up front, since it's the single real gate
in the whole journey (nothing meaningfully starts before the coach has
actually been trained). Everything else is ordered by stage/sort_order
alone; HQ can add finer-grained "Depends On" links later in the Desk if
particular steps need it.
"""

import frappe

ONBOARDING_STEP_DOCTYPE = "Coach Onboarding Master Step"

# (stage_sort_order, stage_label, [(sort_order, step_name, owner_type, where_it_happens, expected_result), ...])
STAGES = [
    (2, "Stage 2 - Get Ready", [
        # "Clothing sizes collected and ordered" is NOT listed here - it's
        # an HQ-only task the coach never sees at all (hidden_from_coach),
        # a field this STAGES tuple format has no slot for. Added directly
        # via add_hq_only_clothing_sizes_step.py instead, same treatment
        # Operations Manual gets for being pulled dynamically rather than
        # fitting this shape.
        (1, "Email account created", "HQ", "Manual / External (email provider)",
         "Coach has a working @resilientkid email."),
        (2, "\"Your Logins\" hub set up", "HQ", "Frappe",
         "One link (theresilienthub.co.uk) + one password gets the coach a page listing every login they "
         "have, plus how-to-access instructions for each."),
        (3, "Frappe Dashboard account created (view access only)", "HQ", "Frappe",
         "Coach can log in and look around/follow along, but can't act on real data yet - no clients exist "
         "for them yet."),
    ]),
    (3, "Stage 3 - Training Day", [
        (1, "Training Day - curriculum, Resilient Kid Values, Resilient Kid Framework, Photoshoot",
         "HQ", "In-Person", ""),
        (2, "Access Your Emails with Chantelle Venter", "Coach", "LMS", "Module marked complete in LMS."),
        # Operations Manual is NOT a static step here - it's pulled live
        # from the coach's own Coach Document Requirement for the
        # Operations Manual Practice Document, same mechanism as Stage 5
        # Policies, just for this one specific document. See
        # _dynamic_operations_manual_step in api/shared/onboarding.py.
    ]),
    (4, "Stage 4 - Get Business Ready", [
        (1, "Social media account created (setup only, not branded)", "HQ", "External (social platform)",
         "Account exists, ready to be branded once photos are back."),
        (2, "HQ processes & delivers photoshoot images", "HQ", "Manual", "Branded photos delivered to the coach."),
        (3, "HQ finalises social media account with branding", "HQ", "External (social platform)",
         "Account fully branded, ready to post."),
        (4, "Email signature set up (with photo)", "HQ", "External (email client)", "Signature added and in use."),
        (5, "Create and order print materials (flyers, business cards, roller banner)", "HQ", "External (print supplier)",
         "Materials ordered and delivered to the coach."),
    ]),
    # Stage 5 - Policies has no static steps here: it's built dynamically
    # from Practice Documents (Policy/Procedure) at read time - see
    # _dynamic_policies_stage() in api/shared/onboarding.py. Kept here
    # (with an empty step list) purely so the stage exists in this map
    # for documentation.
    (5, "Stage 5 - Policies", []),
    (6, "Stage 6 - Get Visible", [
        (1, "Graphics / Canva Training with Sally Tyson", "Coach", "LMS", "Module marked complete in LMS."),
        (2, "Branding Shots for Business with Ali Ford", "Coach", "LMS", "Module marked complete in LMS."),
        (3, "Social Media Training - basics with Lynda Pepper", "Coach", "LMS", "Module marked complete in LMS."),
        (4, "B-Roll Guide for Resilient Kid Coaches", "Coach", "LMS", "Module marked complete in LMS."),
        (5, "LinkedIn Training with Helen Tudor", "Coach", "LMS", "Module marked complete in LMS."),
        (6, "Mission-Led Content with Lisa Barry", "Coach", "LMS", "Module marked complete in LMS."),
        (7, "Talking About Your Business with Catherine Sandland", "Coach", "LMS", "Module marked complete in LMS."),
        (8, "The Stories We Should Be Telling with Catherine Sandland", "Coach", "LMS", "Module marked complete in LMS."),
        (9, "Public Speaking Training with Catherine Sandland", "Coach", "LMS", "Module marked complete in LMS."),
        (10, "The Marketing Momentum Circle with Lisa Barry", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (7, "Stage 7 - Build Your Local Business", [
        (1, "Building a Networking Strategy with Catherine Sandland", "Coach", "LMS", "Module marked complete in LMS."),
        (2, "Networking - the C.O.N.N.E.C.T. Method with Susie Sprigg", "Coach", "LMS", "Module marked complete in LMS."),
        (3, "PR Training with Michelle and Christian Ewan", "Coach", "LMS", "Module marked complete in LMS."),
        (4, "Confidence with Washington Ali", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (8, "Stage 8 - Get Client Ready", [
        (1, "Frappe Training with Chantelle Venter", "Coach", "LMS", "Module marked complete in LMS."),
        (2, "Frappe Dashboard practice (sandbox)", "Coach", "Frappe - coming soon (Tier 3)",
         "Coach can create a lead, send an intake email, have a client complete the form, convert to "
         "Client + Contact, raise an invoice, book an appointment, mark an invoice paid, and view reports "
         "and documents - all against sandbox data, with any triggered email going to the coach's own "
         "address rather than a fictional client."),
        (3, "Onboarding and Offboarding Clients", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (9, "Stage 9 - Learn Your Systems", [
        (1, "Live Frappe follow-up session with Chantelle", "Coach", "In-Person / External",
         "Hands-on session booked with Chantelle and completed, after the LMS module."),
        (2, "Accounting Training with Harriet Parry", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (10, "Stage 10 - Grow", [
        (1, "Business Coaching with Paula Cohen", "Coach", "LMS", "Module marked complete in LMS."),
        (2, "Manage ADHD with Georgia Osborne", "Coach", "LMS", "Module marked complete in LMS."),
        (3, "How to WOW with Nic Welsh", "Coach", "LMS", "Module marked complete in LMS."),
        (4, "Fierce Principles with Sarah Vogel", "Coach", "LMS", "Module marked complete in LMS."),
    ]),
    (11, "Stage 11 - Launch", [
        (1, "Final checks", "HQ", "Manual", "HQ confirms everything required is actually complete."),
        (2, "Coaches Feedback", "Coach", "LMS", "Module marked complete in LMS."),
        (3, "Certification", "Coach", "LMS",
         "Certificate issued - only once everything above is actually complete."),
    ]),
]


def execute():
    if not frappe.db.exists("DocType", ONBOARDING_STEP_DOCTYPE):
        return

    # Seeding the master step list is a one-time convenience, not
    # something the rest of the site depends on to function - if
    # anything here goes wrong, it must never be allowed to fail the
    # whole migrate and roll back the entire deploy again. Worst case
    # HQ adds/edits steps by hand in the Desk, or this patch gets fixed
    # and re-run later.
    try:
        _seed()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "seed_onboarding_steps failed")


def _seed():
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

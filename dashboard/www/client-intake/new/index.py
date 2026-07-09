import frappe


def get_context(context):
    # Public, guest-accessible page - the Lead's own unguessable hash name
    # (?lead=<name>) is the access token, checked by the whitelisted
    # get_intake_lead/submit_intake API calls, not by a login requirement.
    context.no_cache = 1
    context.page_title = "Intake Form"
    context.lead = frappe.form_dict.get("lead") or ""

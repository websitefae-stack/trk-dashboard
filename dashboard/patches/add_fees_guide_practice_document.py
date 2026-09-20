"""
Creates the "Sessional Worker Fees and Expectations Guide" Practice
Document - same pattern as add_franchisee_nda_practice_document.py: lives
in the Practice Documents library so Ashley can edit the wording in
Desk, {{ }} placeholders filled in per-worker at generate/sign time (see
leads.get_fees_guide_sign_url/sign_fees_guide).

{{ franchisee_name }} (the sponsoring Coach's name, looked up from the
lead's own `coach` field), {{ effective_date }}, {{ rate_1to1 }},
{{ rate_group }}, {{ rate_workshop }} and {{ invoicing_frequency }} are
set once by Ashley when she generates the link for a worker (the
sponsoring coach's own business terms); {{ dbs_number }}/
{{ dbs_date_received }}/{{ public_liability_insurer }}/
{{ indemnity_insurer }} are carried over automatically from what the
worker already gave on the Franchisee Intake + DBS/Insurance form, never
re-asked; {{ worker_name }}/{{ worker_signature }}/{{ worker_date }} are
filled in by the worker when they sign, and {{ coach_date }} is the same
effective date the coach set (the coach's side of this is agreeing the
rates and sending the link - see leads.py's _fees_guide_context for why
there's no separate coach signature capture, matching how Ashley's own
"signature" on the NDA/Intent is just her printed name).

Idempotent/safe to leave in place if re-run.
"""

import frappe

PRACTICE_DOCUMENT_DOCTYPE = "Practice Document"
FEES_GUIDE_TITLE = "Sessional Worker Fees and Expectations Guide"

FEES_GUIDE_TEMPLATE_TEXT = """
<h3>The Resilient Kid — Sessional Worker Fees &amp; Expectations Guide</h3>
<p>This guide sets out how you will be paid, what is expected of you, and how you and your
Franchisee work together, alongside your Sessional Worker Agreement. If you have any
questions, speak with your Franchisee in the first instance.</p>

<p><strong>Franchisee:</strong> {{ franchisee_name }}<br>
<strong>Effective from:</strong> {{ effective_date }}</p>

<h4>1. About Your Role</h4>
<p>As a Sessional Worker for The Resilient Kid, you play a vital part in delivering our
children's wellbeing programmes, working under the direction of your Franchisee. You are
engaged on a self-employed, sessional basis:</p>
<ul>
<li>You are not an employee of The Resilient People Limited or your Franchisee.</li>
<li>You will be offered sessions as they arise — you are not guaranteed a minimum number.</li>
<li>You are responsible for your own tax and National Insurance contributions.</li>
<li>You may, with your Franchisee's written agreement, also work with other Resilient Kid
Franchisees in their areas (each a "Contracting Franchisee" for those sessions, responsible for
their own fee to you).</li>
</ul>
<p>Your primary relationship is with your Franchisee, not with The Resilient People Limited.
Day-to-day queries, session bookings, and payments are all managed through your Franchisee.</p>

<h4>2. Your Fees</h4>
<table style="width:100%;border-collapse:collapse;" border="1" cellpadding="6">
<tr><th>Session Type</th><th>Agreed Rate</th></tr>
<tr><td>1:1 Individual Session</td><td>{{ rate_1to1 }}</td></tr>
<tr><td>Small Group Session</td><td>{{ rate_group }}</td></tr>
<tr><td>School / Workshop Session</td><td>{{ rate_workshop }}</td></tr>
</table>
<p>All rates are exclusive of VAT (unless you are VAT-registered). Rates will be reviewed
periodically and any changes communicated to you in writing with reasonable notice.</p>
<p>Your fee covers direct delivery time, reasonable preparation time, and brief post-session
notes. Travel expenses, training day attendance, and materials/resources are not included
unless separately agreed in writing with your Franchisee.</p>

<h4>3. Invoicing and Payment</h4>
<p>After completing sessions, submit an invoice to your Franchisee including your full name and
address, the date(s) and type(s) of session(s) delivered, the agreed rate and total due, your
bank details, and a unique invoice number.</p>
<table style="width:100%;border-collapse:collapse;" border="1" cellpadding="6">
<tr><th>Arrangement</th><th>Detail</th></tr>
<tr><td>Invoicing frequency</td><td>{{ invoicing_frequency }}</td></tr>
<tr><td>Payment terms</td><td>Within 7 days of a valid invoice being received</td></tr>
<tr><td>Payment method</td><td>Bank transfer to your nominated account</td></tr>
</table>
<p>As a self-employed Sessional Worker, you are solely responsible for registering as
self-employed with HMRC, completing your Self Assessment tax return, and paying your own
Income Tax and National Insurance contributions. Neither The Resilient People Limited nor your
Franchisee will make any deductions from your fees.</p>

<h4>4. Brand and Conduct Standards</h4>
<p>When you deliver sessions as a Resilient Kid Sessional Worker, you represent the brand at all
times: dress smartly and appropriately, be punctual, use only approved branded materials and
resources, and identify yourself on written communications as "The Resilient Kid — Sessional
Worker, operating under licence with Ashley Costello". You may not create your own Resilient
Kid branded materials, social media accounts or promotional content without prior written
approval, and must follow the Franchisor's social media policy at all times.</p>

<h4>5. Training Requirements</h4>
<p>Before delivering any sessions, you must complete The Resilient Kid's approved initial
training programme, confirmed in writing by your Franchisee and The Resilient People Limited.
You may be required to attend refresher or additional training during your engagement, up to
five (5) days per year, with reasonable advance notice; training costs and payment are agreed
in writing in advance.</p>

<h4>6. Safeguarding and DBS</h4>
<table style="width:100%;border-collapse:collapse;" border="1" cellpadding="6">
<tr><th>Requirement</th><th>Detail</th></tr>
<tr><td>DBS level required</td><td>Enhanced (with child barring list check)</td></tr>
<tr><td>DBS Certificate number</td><td>{{ dbs_number }}</td></tr>
<tr><td>Date of issue</td><td>{{ dbs_date_received }}</td></tr>
</table>
<p>You must disclose any criminal conviction, caution, reprimand, final warning, police
investigation or pending charges, or any concern raised about your conduct in relation to
children or vulnerable people, to your Franchisee within 48 hours of occurrence. Failure to
disclose may result in immediate suspension and termination of your agreement.</p>
<p>Safeguarding children is everyone's responsibility. You must complete the Franchisor's
safeguarding awareness training before your first session, know and follow the safeguarding
procedure in the Manual, and report any concern about a child's welfare to your Franchisee
immediately. If in doubt, report it.</p>

<h4>7. Availability and Cancellations</h4>
<p>Sessions are offered to you as and when they arise — you are not obliged to accept every
session, and your Franchisee is not obliged to offer a minimum number. Once accepted, you are
committed to delivering it; if you need to cancel, notify your Franchisee as soon as possible
with your reason and agree together whether and how it will be rescheduled.</p>
<p>Keep your Franchisee updated on your general availability, planned holidays, any change in
circumstances affecting your ability to deliver sessions, and any change in your DBS status,
insurance, or professional registrations.</p>

<h4>8. Reporting, Confidentiality and Insurance</h4>
<p>Complete a session record after each session in the format your Franchisee specifies, and
never discuss session content or client details with anyone outside the immediate professional
need. You are required to maintain, throughout your engagement, Public Liability Insurance of
not less than £5,000,000 per claim and Professional Indemnity Insurance in the amount specified
by The Resilient People Limited.</p>
<table style="width:100%;border-collapse:collapse;" border="1" cellpadding="6">
<tr><th>Cover</th><th>Insurer &amp; Policy Number</th></tr>
<tr><td>Public Liability</td><td>{{ public_liability_insurer }}</td></tr>
<tr><td>Professional Indemnity</td><td>{{ indemnity_insurer }}</td></tr>
</table>

<h4>9. Acknowledgement</h4>
<p>By signing below, you confirm that you have read and understood this Fees and Expectations
Guide and agree to work in accordance with its contents alongside your Sessional Worker
Agreement. This document is reviewed periodically by The Resilient People Limited; your
Franchisee will inform you of any updates.</p>

<table style="width:100%;">
<tr>
<td style="width:50%;vertical-align:top;padding-right:20px;">
<p>Sessional Worker full name (print):<br><strong>{{ worker_name }}</strong></p>
<p style="font-style:italic;font-size:22px;">{{ worker_signature }}</p>
<p>{{ worker_date }}<br>Date</p>
</td>
<td style="width:50%;vertical-align:top;">
<p>Franchisee name (print):<br><strong>{{ franchisee_name }}</strong></p>
<p>{{ coach_date }}<br>Date</p>
</td>
</tr>
</table>
"""


def execute():
    if not frappe.db.exists("DocType", PRACTICE_DOCUMENT_DOCTYPE):
        return

    if frappe.db.exists(PRACTICE_DOCUMENT_DOCTYPE, {"document_title": FEES_GUIDE_TITLE}):
        return

    try:
        doc = frappe.get_doc({
            "doctype": PRACTICE_DOCUMENT_DOCTYPE,
            "document_title": FEES_GUIDE_TITLE,
            "document_type": "Agreement",
            "document_purpose": "Internal Compliance",
            "required_action": "Sign",
            "status": "Published",
            "mandatory": 0,
            "document_text": FEES_GUIDE_TEMPLATE_TEXT,
            "signature_statement": (
                "By typing your name below, you confirm you have read and understood this Fees "
                "and Expectations Guide and agree to work in accordance with its contents."
            ),
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "add_fees_guide_practice_document failed")

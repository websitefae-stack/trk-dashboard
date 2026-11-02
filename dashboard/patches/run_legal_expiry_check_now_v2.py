"""
Runs legal_expiry_reminders.send_legal_expiry_reminders() once,
immediately, as part of this deploy - same reasoning as the original
run_legal_expiry_check_now.py, just re-run now that Identification and
Safeguarding Certificate are two more things it checks for coaches
(see add_coach_identification_and_safeguarding_fields.py, which shipped
in a previous deploy via hooks.py's after_migrate - by the time this
patch runs, those fields already exist, so there's no doctype-creation-
ordering risk here the way there was for that one). Every coach
currently has neither on file, so this is what starts their 30-day
grace period from today (Ashley's rule) and sends the first "you have
30 days" reminder, rather than them silently being out of compliance -
with nothing to show for it anywhere in the dashboard - until the next
10am cron tick.

Safe to run in patches.txt (unlike the Table-field patch itself) since
nothing here depends on doctype sync - it only reads/writes Coach
fields that already exist by the time any patch runs.
"""

import frappe

from dashboard.api.shared.legal_expiry_reminders import send_legal_expiry_reminders


def execute():
	if not frappe.db.exists("DocType", "Coach"):
		return

	if not frappe.get_meta("Coach").has_field("safeguarding_certificate_missing_since"):
		# add_coach_identification_and_safeguarding_fields hasn't actually
		# taken effect yet on this site for some reason - safer to skip
		# this run than half-process it; the next day's 10am cron run
		# will pick everything up correctly once it has.
		return

	send_legal_expiry_reminders()

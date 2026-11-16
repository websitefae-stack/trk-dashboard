"""
"why are coach orders not showing in the store" - create_coach_store_
order (webshop_purchase.py) only ever raised a Sales Invoice, never a
Webshop Checkout record, and the Store dashboard's Orders/pack-and-ship
list (store_orders.py) reads exclusively off Webshop Checkout. Fixed
going forward in create_coach_store_order itself (now also creates a
linked "Paid" Webshop Checkout); this backfills one for every Coach
Store order already placed, so past orders become visible and
packable too, not just new ones.

custom_delivery_method is only ever set by create_coach_store_order
(confirmed - the only writer of that field anywhere in this app), so
it's a safe, unique marker for "this Sales Invoice came from the Coach
Store" - never matches an ordinary client invoice.

Safe to re-run - skips any invoice that already has a linked Webshop
Checkout (by invoice name, either direction).
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Webshop Checkout"):
		return

	invoice_meta = frappe.get_meta("Sales Invoice")
	if not invoice_meta.has_field("custom_delivery_method"):
		return

	# custom_coach isn't guaranteed to exist on Sales Invoice either (it
	# doesn't on every site - confirmed live: a migrate crashed selecting
	# it unconditionally) - same has_field guard create_coach_store_order
	# itself already uses before ever setting it.
	has_custom_coach = invoice_meta.has_field("custom_coach")

	fields = ["name", "customer", "currency", "creation", "owner"]
	if has_custom_coach:
		fields.append("custom_coach")

	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"custom_delivery_method": ["is", "set"], "docstatus": 1},
		fields=fields,
	)

	if not invoices:
		return

	already_linked = set(frappe.get_all(
		"Webshop Checkout",
		filters={"invoice": ["in", [inv.name for inv in invoices]]},
		pluck="invoice",
	))

	invoices = [inv for inv in invoices if inv.name not in already_linked]
	if not invoices:
		return

	coach_names = {inv.get("custom_coach") for inv in invoices if inv.get("custom_coach")} if has_custom_coach else set()
	coach_info = {}
	if coach_names:
		for row in frappe.get_all(
			"Coach",
			filters={"name": ["in", list(coach_names)]},
			fields=["name", "coach_name", "user", "coach_email"],
		):
			coach_info[row.name] = row

	# Fallback identity for a site with no custom_coach field at all
	# (confirmed live: a migrate crashed on it - has_custom_coach above)
	# or where it's just blank on a particular invoice - create_coach_
	# store_order always runs under the actual coach's own logged-in
	# session (never impersonated), so Sales Invoice.owner is a
	# reliable stand-in. Without this, every invoice on such a site hit
	# "" for both coach_name and coach_email, which Webshop Checkout
	# then rejected outright (email is mandatory) - the same one
	# invoice failing the same way on every single migrate since,
	# logged forever (confirmed live: 934 occurrences of this exact
	# failure for one invoice, since after_migrate hooks rerun every
	# deploy, not just once like a logged patch).
	owner_coach_by_login = {}
	owners = {inv.owner for inv in invoices if inv.owner and inv.owner != "Administrator"}
	if owners:
		for row in frappe.get_all(
			"Coach",
			filters=[
				["Coach", "user", "in", list(owners)],
				"or",
				["Coach", "coach_email", "in", list(owners)],
			],
			fields=["name", "coach_name", "user", "coach_email"],
		):
			if row.get("user"):
				owner_coach_by_login[row["user"]] = row
			if row.get("coach_email"):
				owner_coach_by_login[row["coach_email"]] = row

	created = 0
	for inv in invoices:
		coach_name = inv.get("custom_coach") if has_custom_coach else None
		coach = coach_info.get(coach_name) or {}

		if not coach and inv.owner:
			coach = owner_coach_by_login.get(inv.owner) or {}
			coach_name = coach.get("name") or coach_name

		coach_display_name = coach.get("coach_name") or coach_name or inv.customer
		# inv.owner itself is always set on any inserted document (never
		# blank) and is a real login email whenever it isn't the
		# Administrator account, so this is the last resort that
		# actually guarantees Webshop Checkout's mandatory email field
		# is never left empty.
		coach_email = coach.get("user") or coach.get("coach_email") or inv.owner or ""

		if not coach_email:
			frappe.log_error(
				f"No owner/coach email at all for {inv.name} - skipped, Webshop Checkout requires one.",
				"Coach Store Order Checkout Backfill Skipped",
			)
			continue

		items = frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": inv.name, "parenttype": "Sales Invoice"},
			fields=["item_code", "item_name", "qty", "rate"],
		)

		if not items:
			continue

		try:
			checkout = frappe.get_doc({
				"doctype": "Webshop Checkout",
				"full_name": coach_display_name,
				"email": coach_email,
				"coach": coach_name or None,
				"status": "Paid",
				"invoice": inv.name,
				"items": [
					{
						"item_code": item.item_code,
						"item_name": item.item_name,
						"qty": item.qty,
						"rate": item.rate,
						"currency": inv.currency or "GBP",
					}
					for item in items
				],
			})
			checkout.insert(ignore_permissions=True)

			# Backdated to the invoice's own creation, purely so the
			# Orders list sorts a backfilled order by when it was
			# actually placed, not by today (when this patch happened
			# to run) - best-effort, never worth losing the checkout
			# record itself over.
			try:
				frappe.db.set_value("Webshop Checkout", checkout.name, "creation", inv.creation, update_modified=False)
			except Exception:
				pass

			created += 1
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Coach Store Order Checkout Backfill Failed - {inv.name}")

	if created:
		frappe.db.commit()

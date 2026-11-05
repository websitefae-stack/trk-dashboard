import frappe
from frappe import _
from frappe.model.document import Document


class AffiliateProductSetting(Document):
	def validate(self):
		if bool(self.item) == bool(self.course):
			frappe.throw(_("Set exactly one of Item or Course, not both or neither."))

		if self.item and frappe.db.get_value("Item", self.item, "has_variants"):
			frappe.throw(_(
				"{0} has variants - set the affiliate commission on it directly and every variant will use "
				"it automatically. A variant template is already the right place for this."
			).format(self.item))

		# Only required while actually enabled - a disabled row (the
		# catalog list's own "turn this back off" state, see
		# affiliate.py's save_affiliate_commission_catalog) can sit at
		# zero with nothing to pay out.
		if not self.enabled:
			return

		if self.commission_type == "Percentage" and not self.commission_percent:
			frappe.throw(_("Set a Commission Percent."))
		if self.commission_type == "Flat Amount" and not self.commission_flat_amount:
			frappe.throw(_("Set a Commission Flat Amount."))

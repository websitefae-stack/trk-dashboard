import frappe
from frappe.model.document import Document


class CalendarSyncLog(Document):
    def before_insert(self):
        if not self.timestamp:
            self.timestamp = frappe.utils.now_datetime()

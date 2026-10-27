import frappe


def execute():
	"""Dreambox's payroll counts attendance from the 19th of the previous month to the 18th."""
	if not frappe.db.get_single_value("HR Settings", "pay_period_start_day"):
		frappe.db.set_single_value("HR Settings", "pay_period_start_day", 19)

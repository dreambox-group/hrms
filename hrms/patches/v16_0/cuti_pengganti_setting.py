import frappe

LEAVE_TYPE = "Cuti Pengganti"


def execute():
	"""Cuti Pengganti: days off for overtime, a leave type of their own that expires 3 months after the
	day worked."""
	if not frappe.db.exists("Leave Type", LEAVE_TYPE):
		frappe.get_doc(
			{
				"doctype": "Leave Type",
				"leave_type_name": LEAVE_TYPE,
				"is_compensatory": 1,
				"include_holiday": 0,
				"is_lwp": 0,
				"allow_negative": 0,
				"calendar_label": LEAVE_TYPE,
			}
		).insert(ignore_permissions=True)

	if not frappe.db.get_single_value("HR Settings", "compensatory_leave_type"):
		frappe.db.set_single_value("HR Settings", "compensatory_leave_type", LEAVE_TYPE)
	if not frappe.db.get_single_value("HR Settings", "compensatory_leave_expiry_months"):
		frappe.db.set_single_value("HR Settings", "compensatory_leave_expiry_months", 3)

	# office check-ins: no Shift Location may allow more than 500 m
	frappe.db.sql("update `tabShift Location` set checkin_radius = 500 where checkin_radius > 500")

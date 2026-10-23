import frappe


def execute():
	# "Requires a Supporting Document" moves from each Leave Type to the HR Settings list, and a
	# request's Document Due date becomes a "Supporting Document Required" flag (no deadline)
	frappe.reload_doc("hr", "doctype", "hr_settings_leave_type")
	frappe.reload_doc("hr", "doctype", "hr_settings")
	frappe.reload_doc("hr", "doctype", "leave_application")

	if frappe.db.has_column("Leave Type", "requires_supporting_document"):
		listed = set(
			frappe.get_all(
				"HR Settings Leave Type",
				filters={"parenttype": "HR Settings", "parentfield": "leave_types_requiring_document"},
				pluck="leave_type",
			)
		)
		new = [
			name
			for name in frappe.get_all(
				"Leave Type", filters={"requires_supporting_document": 1}, pluck="name"
			)
			if name not in listed
		]
		for idx, leave_type in enumerate(new, start=len(listed) + 1):
			frappe.get_doc(
				{
					"doctype": "HR Settings Leave Type",
					"parent": "HR Settings",
					"parenttype": "HR Settings",
					"parentfield": "leave_types_requiring_document",
					"leave_type": leave_type,
					"idx": idx,
				}
			).db_insert()

	if frappe.db.has_column("Leave Application", "document_due_date"):
		frappe.db.sql(
			"update `tabLeave Application` set document_required = 1 where document_due_date is not null"
		)

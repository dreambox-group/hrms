import frappe


def execute():
	# Salary Slips are shown in the employee app (HR can turn them off again in HR Settings);
	# a patch runs once per site, so this doesn't undo a later choice
	frappe.db.set_single_value("HR Settings", "show_salary_in_employee_app", 1)

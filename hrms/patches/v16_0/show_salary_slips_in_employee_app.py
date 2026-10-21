import frappe


def execute():
	# Salary Slips are shown in the employee app unless HR has turned them off
	if frappe.db.get_single_value("HR Settings", "show_salary_in_employee_app") is None:
		frappe.db.set_single_value("HR Settings", "show_salary_in_employee_app", 1)

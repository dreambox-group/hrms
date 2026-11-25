import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hrms.setup import get_additional_department_fields


def execute():
	# Employee > Secondary Departments (hrms.hr.supervisors.get_team; owner, 25 Nov 2026)
	frappe.reload_doc("hr", "doctype", "employee_additional_department")
	create_custom_fields({"Employee": get_additional_department_fields()}, ignore_validate=True)

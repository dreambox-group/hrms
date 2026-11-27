from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hrms.setup import get_drea_payroll_fields


def execute():
	# Employee > PTKP Status, Payroll Settings > Calculate PPh 21 (off), Salary Slip > PPh 21 Working
	# (hrms.payroll.drea_pph21; owner, 27 Nov 2026)
	create_custom_fields(get_drea_payroll_fields(), ignore_validate=True)

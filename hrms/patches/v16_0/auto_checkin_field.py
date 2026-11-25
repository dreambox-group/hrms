from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hrms.setup import get_auto_checkin_fields


def execute():
	# Employee > Attendance & Leaves: Automatic Check-in (hrms.hr.auto_checkin)
	create_custom_fields({"Employee": get_auto_checkin_fields()}, ignore_validate=True)

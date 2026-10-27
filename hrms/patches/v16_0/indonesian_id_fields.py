from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hrms.setup import get_indonesian_id_fields


def execute():
	# kept by the old HRIS; Old HRIS Import fills them
	create_custom_fields({"Employee": get_indonesian_id_fields()}, ignore_validate=True)

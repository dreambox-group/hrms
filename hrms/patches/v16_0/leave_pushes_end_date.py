import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hrms.hr.doctype.leave_application.leave_end_date import start_counting_for_types
from hrms.setup import get_leave_end_date_fields

LEAVE_TYPE = "Leave without Allocation"


def execute():
	# Employee fields for "Employee Types without Leave Allocation"; Intern is the first such type
	create_custom_fields({"Employee": get_leave_end_date_fields()}, ignore_validate=True)

	# their leave type: needs no allocation (Allow Negative Balance) and doesn't cut pay (not LWP)
	if not frappe.db.exists("Leave Type", {"allow_negative": 1, "is_lwp": 0}):
		frappe.get_doc(
			{
				"doctype": "Leave Type",
				"leave_type_name": LEAVE_TYPE,
				"allow_negative": 1,
				"is_lwp": 0,
				"include_holiday": 0,
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Employment Type", "Intern"):
		return
	settings = frappe.get_single("HR Settings")
	if "Intern" in {row.employment_type for row in settings.employment_types_without_leave_allocation}:
		return
	frappe.get_doc(
		{
			"doctype": "HR Settings Employment Type",
			"parent": "HR Settings",
			"parenttype": "HR Settings",
			"parentfield": "employment_types_without_leave_allocation",
			"employment_type": "Intern",
			"idx": len(settings.employment_types_without_leave_allocation) + 1,
		}
	).db_insert()
	# current interns count leave from today, so leave they already took isn't added on top
	start_counting_for_types({"Intern"})

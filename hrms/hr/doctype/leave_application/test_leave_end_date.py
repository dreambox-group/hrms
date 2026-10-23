# Copyright (c) 2026, Dreambox and contributors
# See license.txt

import frappe
from frappe.utils import add_days, getdate, nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.api import get_leave_types
from hrms.hr.doctype.leave_application.leave_end_date import add_working_days, end_date_details
from hrms.tests.utils import HRMSTestSuite
from hrms.utils.holiday_list import get_holiday_dates_between_range

COMPANY = "_Test Company"
TYPE = "_Test Fixed Term"
OTHER_TYPE = "_Test Permanent"
NO_ALLOCATION_LEAVE = "_Test No Allocation Leave"


class TestLeaveEndDate(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		for name in (TYPE, OTHER_TYPE):
			if not frappe.db.exists("Employment Type", name):
				frappe.get_doc({"doctype": "Employment Type", "employee_type_name": name}).insert()
		if not frappe.db.exists("Leave Type", NO_ALLOCATION_LEAVE):
			frappe.get_doc(
				{
					"doctype": "Leave Type",
					"leave_type_name": NO_ALLOCATION_LEAVE,
					"allow_negative": 1,
					"is_lwp": 0,
					"include_holiday": 0,
				}
			).insert()
		set_types_without_allocation([TYPE])
		self.end = add_days(getdate(), 90)

	def tearDown(self):
		frappe.set_user("Administrator")
		set_types_without_allocation([])

	def employee(self, user, employment_type=TYPE, contract_end_date=None):
		name = make_employee(f"{user}@example.com", COMPANY)
		# a clean slate on every run
		for doctype in ("Leave Application", "Leave Ledger Entry", "Leave Allocation"):
			frappe.db.delete(doctype, {"employee": name})
		doc = frappe.get_doc("Employee", name)
		doc.employment_type = employment_type
		doc.contract_end_date = contract_end_date or self.end
		doc.original_contract_end_date = None
		doc.leave_counted_from = None
		doc.save()
		return name

	def test_new_type_member_starts_counting_today(self):
		employee = self.employee("le.start")
		row = frappe.db.get_value(
			"Employee", employee, ["original_contract_end_date", "leave_counted_from"], as_dict=True
		)
		self.assertEqual(getdate(row.original_contract_end_date), self.end)
		self.assertEqual(getdate(row.leave_counted_from), getdate())

	def test_approved_leave_moves_the_end_date_and_cancel_moves_it_back(self):
		employee = self.employee("le.move")
		leave = approve(employee, *working_days_ahead(employee, 3))

		end = contract_end(employee)
		self.assertEqual(end, add_working_days(employee, self.end, 3))
		self.assertEqual(working_days_between(employee, self.end, end), 3)
		self.assertTrue(
			frappe.db.exists(
				"Comment", {"reference_name": employee, "content": ("like", "Contract end moved%")}
			)
		)

		leave.cancel()
		self.assertEqual(contract_end(employee), self.end)

	def test_half_days_round_up(self):
		employee = self.employee("le.half")
		first, second = working_days_ahead(employee, 2)
		approve(employee, first, first, half_day=True)
		self.assertEqual(contract_end(employee), add_working_days(employee, self.end, 1))

		approve(employee, second, second)  # 1.5 days in total -> 2
		self.assertEqual(contract_end(employee), add_working_days(employee, self.end, 2))

	def test_rejected_leave_and_other_types_change_nothing(self):
		employee = self.employee("le.reject")
		application = apply(employee, *working_days_ahead(employee, 1))
		application.status = "Rejected"
		application.submit()
		self.assertEqual(contract_end(employee), self.end)

		permanent = self.employee("le.permanent", OTHER_TYPE)
		frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": permanent,
				"leave_type": NO_ALLOCATION_LEAVE,
				"from_date": getdate(),
				"to_date": add_days(getdate(), 200),
				"new_leaves_allocated": 5,
			}
		).submit()
		approve(permanent, *working_days_ahead(permanent, 1))
		self.assertEqual(contract_end(permanent), self.end)

	def test_leave_before_leave_counted_from_is_not_counted(self):
		employee = self.employee("le.counted")
		start, end = working_days_ahead(employee, 2)
		frappe.db.set_value("Employee", employee, "leave_counted_from", add_days(end, 1))
		approve(employee, start, end)
		self.assertEqual(contract_end(employee), self.end)

	def test_hand_edited_end_date_is_a_renewal(self):
		employee = self.employee("le.renew")
		approve(employee, *working_days_ahead(employee, 1))

		renewed = add_days(self.end, 180)
		doc = frappe.get_doc("Employee", employee)
		doc.contract_end_date = renewed
		doc.save()
		doc.reload()
		self.assertEqual(getdate(doc.original_contract_end_date), renewed)
		self.assertEqual(getdate(doc.contract_end_date), renewed)
		self.assertEqual(getdate(doc.leave_counted_from), getdate())

	def test_cleared_fields_start_again(self):
		employee = self.employee("le.cleared")
		approve(employee, *working_days_ahead(employee, 2))
		moved = contract_end(employee)
		doc = frappe.get_doc("Employee", employee)
		doc.original_contract_end_date = None
		doc.leave_counted_from = None
		doc.save()
		self.assertEqual(getdate(doc.original_contract_end_date), moved)
		self.assertEqual(getdate(doc.leave_counted_from), getdate())

	def test_editing_the_original_date_recalculates(self):
		employee = self.employee("le.original")
		approve(employee, *working_days_ahead(employee, 2))
		doc = frappe.get_doc("Employee", employee)
		doc.original_contract_end_date = add_days(self.end, 30)
		doc.save()
		self.assertEqual(
			getdate(doc.contract_end_date), add_working_days(employee, add_days(self.end, 30), 2)
		)

	def test_no_allocation_for_types_in_the_list(self):
		employee = self.employee("le.alloc")
		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee,
				"leave_type": NO_ALLOCATION_LEAVE,
				"from_date": getdate(),
				"to_date": add_days(getdate(), 200),
				"new_leaves_allocated": 5,
			}
		)
		self.assertRaises(frappe.ValidationError, allocation.insert)

	def test_leave_types_offered(self):
		employee = self.employee("le.types")
		types = get_leave_types(employee, nowdate())
		self.assertIn(NO_ALLOCATION_LEAVE, types)
		self.assertNotIn("Leave Without Pay", types)

	def test_preview(self):
		employee = self.employee("le.preview")
		details = end_date_details(employee, 2)
		self.assertEqual(getdate(details.end_date_after), add_working_days(employee, self.end, 2))
		self.assertEqual(details.days_moved, 0)

	def test_adding_a_type_starts_counting_for_its_employees(self):
		employee = self.employee("le.added", OTHER_TYPE)
		frappe.db.set_value(
			"Employee", employee, {"original_contract_end_date": None, "leave_counted_from": None}
		)
		set_types_without_allocation([TYPE, OTHER_TYPE])
		self.assertEqual(getdate(frappe.db.get_value("Employee", employee, "leave_counted_from")), getdate())

	def test_only_hr_changes_the_fields(self):
		employee = self.employee("le.self")
		frappe.set_user("le.self@example.com")
		doc = frappe.get_doc("Employee", employee)
		doc.original_contract_end_date = add_days(self.end, 365)
		self.assertRaises((frappe.ValidationError, frappe.PermissionError), doc.save)


def set_types_without_allocation(types):
	settings = frappe.get_single("HR Settings")
	settings.employment_types_without_leave_allocation = []
	for employment_type in types:
		settings.append("employment_types_without_leave_allocation", {"employment_type": employment_type})
	settings.save()


def contract_end(employee):
	return getdate(frappe.db.get_value("Employee", employee, "contract_end_date"))


def holidays(employee, start, end):
	return {
		getdate(d)
		for d in get_holiday_dates_between_range(employee, start, end, raise_exception_for_holiday_list=False)
	}


def working_days_ahead(employee, count):
	"""The first and last of `count` working days starting next week (no holidays in between)."""
	start = add_days(getdate(), 7)
	off = holidays(employee, start, add_days(start, 60))
	days = []
	date = start
	while len(days) < count:
		if date not in off:
			days.append(date)
		elif days:
			days = []  # keep the run free of holidays so the leave counts every day
		date = add_days(date, 1)
	return days[0], days[-1]


def working_days_between(employee, start, end):
	off = holidays(employee, add_days(start, 1), end)
	return len(
		[
			d
			for d in (add_days(getdate(start), n) for n in range(1, (getdate(end) - getdate(start)).days + 1))
			if d not in off
		]
	)


def apply(employee, from_date, to_date, half_day=False):
	return frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": NO_ALLOCATION_LEAVE,
			"from_date": from_date,
			"to_date": to_date,
			"half_day": 1 if half_day else 0,
			"half_day_date": from_date if half_day else None,
			"company": COMPANY,
			"posting_date": nowdate(),
		}
	).insert()


def approve(employee, from_date, to_date, half_day=False):
	application = apply(employee, from_date, to_date, half_day)
	application.status = "Approved"
	application.submit()
	return application

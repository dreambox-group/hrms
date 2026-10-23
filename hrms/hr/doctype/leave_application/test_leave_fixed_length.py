# Copyright (c) 2026, Dreambox and contributors
# See license.txt

import frappe
from frappe.utils import add_days, getdate, nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.api import get_leave_types
from hrms.hr.doctype.leave_application.leave_fixed_length import fixed_end_date
from hrms.tests.utils import HRMSTestSuite
from hrms.utils.holiday_list import get_holiday_dates_between_range

COMPANY = "_Test Company"
SICK = "_Test Fixed Sick Leave"
BIRTH = "_Test Fixed After-birth Leave"
CALENDAR = "_Test Fixed Calendar Leave"


class TestLeaveFixedLength(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		for name, include_holiday in ((SICK, 0), (BIRTH, 1), (CALENDAR, 1)):
			if not frappe.db.exists("Leave Type", name):
				frappe.get_doc(
					{"doctype": "Leave Type", "leave_type_name": name, "include_holiday": include_holiday}
				).insert()
		set_fixed_lengths([(SICK, 2, "Days"), (BIRTH, 3, "Months"), (CALENDAR, 5, "Days")])
		self.employee = make_employee("fl.staff@example.com", COMPANY)
		frappe.db.set_value("Employee", self.employee, "employment_type", None)
		for doctype in ("Leave Application", "Leave Ledger Entry", "Leave Allocation"):
			frappe.db.delete(doctype, {"employee": self.employee})

	def tearDown(self):
		frappe.set_user("Administrator")
		set_fixed_lengths([])

	def test_working_days_skip_holidays(self):
		start = next_working_day(self.employee)
		leave = apply(self.employee, SICK, start, add_days(start, 20))
		self.assertEqual(getdate(leave.to_date), fixed_end_date(self.employee, SICK, start))
		self.assertEqual(leave.total_leave_days, 2)
		self.assertEqual(working_days(self.employee, start, leave.to_date), 2)

	def test_calendar_days_with_include_holidays(self):
		start = next_working_day(self.employee)
		leave = apply(self.employee, CALENDAR, start, start)
		self.assertEqual(getdate(leave.to_date), add_days(start, 4))

	def test_months_are_calendar_months(self):
		self.assertEqual(fixed_end_date(self.employee, BIRTH, "2026-11-01"), getdate("2027-01-31"))
		self.assertEqual(fixed_end_date(self.employee, BIRTH, "2026-11-15"), getdate("2027-02-14"))
		start = next_working_day(self.employee)
		leave = apply(self.employee, BIRTH, start, start)
		self.assertEqual(getdate(leave.to_date), fixed_end_date(self.employee, BIRTH, start))

	def test_no_half_days(self):
		start = next_working_day(self.employee)
		leave = apply(self.employee, SICK, start, start, half_day=True)
		self.assertFalse(leave.half_day)
		self.assertEqual(leave.total_leave_days, 2)

	def test_no_allocation_needed_and_offered_to_everyone(self):
		self.assertIn(SICK, get_leave_types(self.employee, nowdate()))
		start = next_working_day(self.employee)
		leave = apply(self.employee, SICK, start, start)
		leave.status = "Approved"
		leave.submit()
		self.assertEqual(leave.docstatus, 1)

	def test_an_allocation_still_counts(self):
		start = next_working_day(self.employee)
		frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": self.employee,
				"leave_type": SICK,
				"from_date": add_days(getdate(), -1),
				"to_date": add_days(getdate(), 200),
				"new_leaves_allocated": 1,
			}
		).submit()
		self.assertRaises(frappe.ValidationError, apply, self.employee, SICK, start, start)

	def test_other_leave_types_unchanged(self):
		self.assertIsNone(fixed_end_date(self.employee, "_Test Leave Type", nowdate()))

	def test_settings_refuse_duplicates_and_zero(self):
		self.assertRaises(frappe.ValidationError, set_fixed_lengths, [(SICK, 2, "Days"), (SICK, 3, "Days")])
		self.assertRaises(frappe.ValidationError, set_fixed_lengths, [(SICK, 0, "Days")])


def set_fixed_lengths(rows):
	settings = frappe.get_single("HR Settings")
	settings.leave_types_with_fixed_length = []
	for leave_type, length, unit in rows:
		settings.append(
			"leave_types_with_fixed_length", {"leave_type": leave_type, "length": length, "unit": unit}
		)
	settings.save()


def holidays(employee, start, end):
	return {
		getdate(d)
		for d in get_holiday_dates_between_range(employee, start, end, raise_exception_for_holiday_list=False)
	}


def next_working_day(employee):
	date = add_days(getdate(), 10)
	off = holidays(employee, date, add_days(date, 30))
	while date in off:
		date = add_days(date, 1)
	return date


def working_days(employee, start, end):
	off = holidays(employee, start, end)
	days = (getdate(end) - getdate(start)).days + 1
	return len([d for d in (add_days(getdate(start), n) for n in range(days)) if d not in off])


def apply(employee, leave_type, from_date, to_date, half_day=False):
	return frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": leave_type,
			"from_date": from_date,
			"to_date": to_date,
			"half_day": 1 if half_day else 0,
			"half_day_date": from_date if half_day else None,
			"company": COMPANY,
			"posting_date": nowdate(),
		}
	).insert()

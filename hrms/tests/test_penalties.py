# Copyright (c) 2026, Dreambox and contributors
# See license.txt

from datetime import datetime, time

import frappe
from frappe.utils import add_days, add_months, get_year_ending, get_year_start, getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.employee_checkin.test_employee_checkin import make_checkin
from hrms.hr.doctype.shift_type.test_shift_type import setup_shift_type
from hrms.hr.penalties import get_pay_period, get_penalties
from hrms.tests.utils import HRMSTestSuite

COMPANY = "_Test Company"
HOLIDAY_LIST = "_Test Penalties No Holidays"
LWP = "_Test Penalties LWP"


class TestPenalties(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)
		# a month ago, so every day counted is in the past
		self.month = add_months(getdate(), -1).replace(day=1)
		if not frappe.db.exists("Holiday List", HOLIDAY_LIST):
			frappe.get_doc(
				{
					"doctype": "Holiday List",
					"holiday_list_name": HOLIDAY_LIST,
					"from_date": get_year_start(add_months(getdate(), -12)),
					"to_date": get_year_ending(getdate()),
				}
			).insert()
		if not frappe.db.exists("Leave Type", LWP):
			# counts every day, so the test doesn't depend on weekdays
			frappe.get_doc(
				{"doctype": "Leave Type", "leave_type_name": LWP, "is_lwp": 1, "include_holiday": 1}
			).insert()
		shift = setup_shift_type(shift_type="_Test Penalties Shift", start_time="08:00:00", end_time="17:00:00")
		frappe.db.set_value(
			"Shift Type", shift.name, {"enable_late_entry_marking": 1, "late_entry_grace_period": 15}
		)
		self.employee = make_employee(
			"pen.staff@example.com", COMPANY, holiday_list=HOLIDAY_LIST, default_shift=shift.name
		)
		frappe.db.set_value("Employee", self.employee, "date_of_joining", add_months(self.month, -6))
		for doctype in ("Employee Checkin", "Leave Application", "Leave Ledger Entry", "Attendance"):
			frappe.db.delete(doctype, {"employee": self.employee})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "pay_period_start_day", 0)

	def day(self, n):
		return add_days(self.month, n - 1)

	def test_pay_period(self):
		frappe.db.set_single_value("HR Settings", "pay_period_start_day", 19)
		self.assertEqual(get_pay_period("2026-10-27"), (getdate("2026-10-19"), getdate("2026-11-18")))
		self.assertEqual(get_pay_period("2026-10-05"), (getdate("2026-09-19"), getdate("2026-10-18")))
		self.assertEqual(get_pay_period("2026-01-18"), (getdate("2025-12-19"), getdate("2026-01-18")))

		# not set or 1: calendar months
		frappe.db.set_single_value("HR Settings", "pay_period_start_day", 0)
		self.assertEqual(get_pay_period("2026-02-10"), (getdate("2026-02-01"), getdate("2026-02-28")))

	def test_counts_this_period(self):
		frappe.db.set_single_value("HR Settings", "pay_period_start_day", 1)
		make_checkin(self.employee, datetime.combine(self.day(2), time(8, 10)))
		make_checkin(self.employee, datetime.combine(self.day(3), time(8, 40)))
		# "today" (the 10th): late counts, but not checking in yet doesn't
		make_checkin(self.employee, datetime.combine(self.day(10), time(8, 50)))
		leave = frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": self.employee,
				"leave_type": LWP,
				"from_date": self.day(5),
				"to_date": self.day(6),
				"company": COMPANY,
				"status": "Approved",
			}
		).insert()
		leave.submit()

		penalties = get_penalties(self.employee, self.day(10))
		self.assertEqual(penalties["period_start"], self.month)
		self.assertEqual(penalties["late"], [self.day(3), self.day(10)])
		self.assertEqual(penalties["no_checkin"], [self.day(n) for n in (1, 4, 7, 8, 9)])
		self.assertEqual([row["days"] for row in penalties["unpaid_leave"]], [2])

		# marked attendance wins over the check-in
		attendance = frappe.get_doc(
			{
				"doctype": "Attendance",
				"employee": self.employee,
				"attendance_date": self.day(4),
				"status": "Present",
				"late_entry": 1,
				"company": COMPANY,
			}
		).insert()
		attendance.submit()
		penalties = get_penalties(self.employee, self.day(10))
		self.assertEqual(penalties["late"], [self.day(3), self.day(4), self.day(10)])
		self.assertNotIn(self.day(4), penalties["no_checkin"])

# Copyright (c) 2026, Dreambox and contributors
# See license.txt

from datetime import datetime, time

import frappe
from frappe.utils import add_days, add_years, get_year_ending, get_year_start, getdate, nowdate

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.api.employee_app import (
	get_attendance_month,
	get_notifications,
	get_upcoming_holidays,
	mark_notification_as_read,
)
from hrms.api.home import get_home_data
from hrms.api.hr_dashboard import get_dashboard_data
from hrms.hr.doctype.employee_checkin.test_employee_checkin import make_checkin
from hrms.hr.doctype.leave_application.test_leave_application import make_allocation_record
from hrms.hr.doctype.shift_type.test_shift_type import setup_shift_type
from hrms.hr.workforce_today import get_active_employees, get_celebrations, get_workforce_today
from hrms.tests.utils import HRMSTestSuite

COMPANY = "_Test Company"
HOLIDAY_LIST = "Employee Checkin Test Holiday List"


class TestHRFrontends(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		self.shift = setup_shift_type(
			shift_type="_Test Frontends Shift", start_time="08:00:00", end_time="17:00:00"
		)
		frappe.db.set_value(
			"Shift Type", self.shift.name, {"enable_late_entry_marking": 1, "late_entry_grace_period": 15}
		)
		self.department = make_department("_Test FE Team", approvers=["fe.approver@example.com"])
		for user in ("fe.ontime", "fe.late", "fe.away", "fe.notin"):
			self.employee(user, default_shift=self.shift.name)
		self.employee("fe.noshift")
		clear_test_records(self.department)

	def tearDown(self):
		frappe.set_user("Administrator")

	def employee(self, user, **kwargs):
		return make_employee(
			f"{user}@example.com", COMPANY, department=self.department, holiday_list=HOLIDAY_LIST, **kwargs
		)

	def test_workforce_today(self):
		date = getdate()
		make_checkin(self.employee("fe.ontime"), datetime.combine(date, time(8, 10)))
		make_checkin(self.employee("fe.late"), datetime.combine(date, time(8, 40)))
		approve_leave(self.employee("fe.away"), date)

		statuses = {
			row.employee_name: row.status
			for row in get_workforce_today(get_active_employees(departments=[self.department]), date)
		}
		self.assertEqual(statuses["fe.ontime@example.com"], "Checked in")
		self.assertEqual(statuses["fe.late@example.com"], "Late")
		self.assertEqual(statuses["fe.away@example.com"], "On leave")
		self.assertEqual(statuses["fe.notin@example.com"], "Not yet in")
		self.assertEqual(statuses["fe.noshift@example.com"], "No shift")

	def test_celebrations(self):
		date = getdate()
		frappe.db.set_value(
			"Employee",
			self.employee("fe.ontime"),
			{"date_of_birth": add_years(add_days(date, 2), -30), "date_of_joining": add_years(date, -3)},
		)
		celebrations = [
			(c.employee_name, c.kind, c.get("years"))
			for c in get_celebrations(get_active_employees(departments=[self.department]), 7, date)
		]
		self.assertIn(("fe.ontime@example.com", "Birthday", None), celebrations)
		self.assertIn(("fe.ontime@example.com", "Work anniversary", 3), celebrations)

	def test_dashboard_is_for_hr_only(self):
		frappe.set_user("fe.notin@example.com")
		self.assertRaises(frappe.PermissionError, get_dashboard_data)

		frappe.set_user("Administrator")
		data = get_dashboard_data(COMPANY)
		for key in (
			"stats",
			"attendance",
			"leave",
			"away",
			"celebrations",
			"shifts",
			"headcount",
			"changes",
			"requests",
		):
			self.assertIn(key, data)
		self.assertIn(COMPANY, data["companies"])
		self.assertIn(self.department, [h["department"] for h in data["headcount"]])

	def test_dashboard_lists_waiting_leave_with_its_approver(self):
		application = apply_for_leave(
			self.employee("fe.notin"), add_days(getdate(), 7), "fe.approver@example.com"
		)

		waiting = {row.name: row for row in get_dashboard_data(COMPANY)["leave"]["waiting"]}
		self.assertIn(application.name, waiting)
		self.assertTrue(waiting[application.name].progress[0].startswith("Approver:"))

	def test_home_for_a_leave_approver(self):
		approver = self.employee("fe.approver")
		application = apply_for_leave(
			self.employee("fe.notin"), add_days(getdate(), 7), "fe.approver@example.com"
		)
		make_checkin(self.employee("fe.ontime"), datetime.combine(getdate(), time(8, 5)))

		frappe.set_user("fe.approver@example.com")
		data = get_home_data()

		self.assertIn(application.name, [row.name for row in data["leave_approvals"]])
		team = data["team"]
		self.assertEqual(team["departments"], [self.department])
		# the approver isn't in their own team list
		self.assertNotIn(approver, [row.employee for row in team["rows"]])
		self.assertEqual(team["checked_in"], 1)

	def test_home_for_staff(self):
		approve_leave(self.employee("fe.away"), getdate())

		frappe.set_user("fe.notin@example.com")
		data = get_home_data()

		self.assertIsNone(data["team"])
		self.assertFalse(data["leave_approvals"])
		self.assertIn("fe.away@example.com", [row["employee_name"] for row in data["on_leave_today"]])

	def test_home_shows_my_own_day(self):
		date = getdate()
		make_checkin(self.employee("fe.late"), datetime.combine(date, time(8, 40)))

		frappe.set_user("fe.late@example.com")
		me = get_home_data()["me"]

		self.assertEqual(me.status, "Late")
		self.assertEqual(me.checked_in_at, datetime.combine(date, time(8, 40)))
		# shift starts 08:00 with 15 minutes' grace
		self.assertEqual(me.late_after, datetime.combine(date, time(8, 15)))
		self.assertIsNotNone(me.opens_at)

	def test_attendance_month_is_the_users_own(self):
		date = getdate()
		make_checkin(self.employee("fe.ontime"), datetime.combine(date, time(8, 10)))
		make_checkin(self.employee("fe.late"), datetime.combine(date, time(7, 50)))

		frappe.set_user("fe.ontime@example.com")
		days = {getdate(row["date"]): row for row in get_attendance_month(str(add_days(date, -6)), str(date))}

		self.assertEqual(len(days), 7)
		self.assertEqual(days[date]["checked_in_at"], datetime.combine(date, time(8, 10)))
		self.assertRaises(frappe.ValidationError, get_attendance_month, str(add_days(date, -90)), str(date))

	def test_upcoming_holidays_earliest_first(self):
		employee = self.employee("fe.ontime")
		# the list in effect (a Holiday List Assignment can override the Employee field)
		holiday_list = frappe.get_doc("Holiday List", get_holiday_list_for_employee(employee))
		# days the list doesn't have yet (weekends are usually there already as weekly days off)
		free = [
			date
			for date in (add_days(getdate(), n) for n in range(-10, 60))
			if not frappe.db.exists("Holiday", {"parent": holiday_list.name, "holiday_date": date})
		]
		dates = [free[-1], next(d for d in free if d > getdate()), free[0]]
		for offset, date in enumerate(dates):
			if not frappe.db.exists("Holiday", {"parent": holiday_list.name, "holiday_date": date}):
				holiday_list.append("holidays", {"holiday_date": date, "description": f"FE holiday {offset}"})
		holiday_list.to_date = max(holiday_list.to_date, dates[0])
		holiday_list.save()

		frappe.set_user("fe.ontime@example.com")
		holidays = get_upcoming_holidays()
		holiday_dates = [getdate(row.holiday_date) for row in holidays]
		self.assertEqual(holiday_dates, sorted(holiday_dates))
		self.assertTrue(all(date >= getdate() for date in holiday_dates))
		self.assertIn(dates[1], holiday_dates)
		self.assertEqual(getdate(get_home_data()["next_holiday"].holiday_date), holiday_dates[0])

	def test_notifications_are_the_users_own(self):
		self.employee("fe.ontime")
		self.employee("fe.late")
		mine = make_notification("fe.ontime@example.com")
		theirs = make_notification("fe.late@example.com")

		frappe.set_user("fe.ontime@example.com")
		names = [row.name for row in get_notifications()]
		self.assertIn(mine, names)
		self.assertNotIn(theirs, names)

		mark_notification_as_read(mine)
		self.assertEqual(frappe.db.get_value("PWA Notification", mine, "read"), 1)
		self.assertRaises(frappe.PermissionError, mark_notification_as_read, theirs)


def make_notification(to_user):
	return (
		frappe.get_doc(
			{
				"doctype": "PWA Notification",
				"to_user": to_user,
				"from_user": "Administrator",
				"message": "Test notification",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def make_department(name, approvers=()):
	department = frappe.db.get_value("Department", {"department_name": name, "company": COMPANY})
	department = (
		frappe.get_doc("Department", department)
		if department
		else frappe.get_doc({"doctype": "Department", "department_name": name, "company": COMPANY})
	)
	department.leave_approvers = []
	for user in approvers:
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": user.split("@")[0], "send_welcome_email": 0}
			).insert()
		department.append("leave_approvers", {"approver": user})
	department.save()
	return department.name


def clear_test_records(department):
	employees = frappe.get_all("Employee", filters={"department": department}, pluck="name")
	if not employees:
		return
	applications = frappe.get_all("Leave Application", filters={"employee": ("in", employees)}, pluck="name")
	if applications:
		frappe.db.delete("Leave Application", {"name": ("in", applications)})
	frappe.db.delete(
		"Leave Ledger Entry", {"employee": ("in", employees), "transaction_type": "Leave Application"}
	)
	frappe.db.delete("Employee Checkin", {"employee": ("in", employees)})


def ensure_allocation(employee, date):
	if not frappe.db.exists(
		"Leave Allocation",
		{"employee": employee, "leave_type": "_Test Leave Type", "docstatus": 1, "to_date": (">=", date)},
	):
		make_allocation_record(employee, from_date=get_year_start(date), to_date=get_year_ending(date))


def apply_for_leave(employee, date, leave_approver=None):
	ensure_allocation(employee, date)
	return frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": "_Test Leave Type",
			"from_date": date,
			"to_date": date,
			"company": COMPANY,
			"posting_date": nowdate(),
			"leave_approver": leave_approver,
		}
	).insert()


def approve_leave(employee, date):
	application = apply_for_leave(employee, date)
	application.status = "Approved"
	application.submit()
	return application

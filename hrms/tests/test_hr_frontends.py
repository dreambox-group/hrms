# Copyright (c) 2026, Dreambox and contributors
# See license.txt

from datetime import datetime, time

import frappe
from frappe.utils import add_days, add_years, get_year_ending, get_year_start, getdate, nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

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

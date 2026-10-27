# Copyright (c) 2026, Dreambox and contributors
# See license.txt

import frappe
from frappe.utils import add_days, get_year_ending, get_year_start, getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.api.employee_app import (
	get_attendance_month,
	get_my_leave_changes,
	get_team_attendance,
	get_team_leave_history,
	request_leave_change,
	withdraw_leave_change,
)
from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
from hrms.hr.doctype.leave_application.test_leave_application import make_allocation_record
from hrms.hr.doctype.leave_application.test_leave_approval_levels import decide, make_department
from hrms.hr.doctype.leave_change_request.leave_change_request import LeaveChangeRequestError
from hrms.hr.utils import get_holiday_dates_for_employee
from hrms.tests.utils import HRMSTestSuite, make_user

COMPANY = "_Test Company"
LEAVE_TYPE = "_Test Leave Type"
STAFF = "lc.staff@example.com"
COLLEAGUE = "lc.colleague@example.com"
HEAD = "lc.head@example.com"
OUTSIDER = "lc.outsider@example.com"
HR = "lc.hr@example.com"


class TestLeaveChangeRequest(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 1)
		self.department = make_department("_Test LC Team", approvers=[(HEAD, "Required")])
		make_department("_Test LC Elsewhere", approvers=[(OUTSIDER, "Required")])
		self.employee = make_employee(STAFF, COMPANY, department=self.department)
		self.colleague = make_employee(COLLEAGUE, COMPANY, department=self.department)
		make_user(HR, "HR User")
		for employee in (self.employee, self.colleague):
			applications = frappe.get_all("Leave Application", filters={"employee": employee}, pluck="name")
			frappe.db.delete("Leave Application Approver", {"parent": ("in", applications or [""])})
			for doctype in ("Leave Change Request", "Leave Application", "Leave Ledger Entry", "Leave Allocation"):
				frappe.db.delete(doctype, {"employee": employee})
		self.days = working_days(self.employee, 3)
		make_allocation_record(
			self.employee, from_date=get_year_start(self.days[0]), to_date=get_year_ending(self.days[-1])
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)

	def approved_leave(self, date):
		leave = frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": self.employee,
				"leave_type": LEAVE_TYPE,
				"from_date": date,
				"to_date": date,
				"company": COMPANY,
			}
		).insert()
		decide(leave, HEAD, "Approved")
		leave.reload()
		self.assertEqual((leave.docstatus, leave.status), (1, "Approved"))
		return leave

	def ask(self, leave, change="Cancel the leave", checklist=True, **dates):
		frappe.set_user(STAFF)
		try:
			return request_leave_change(
				leave.name,
				change,
				"Family plans changed",
				informed_hr=int(checklist),
				understands_waiting=int(checklist),
				**dates,
			)
		finally:
			frappe.set_user("Administrator")

	def decide_as_hr(self, name, decision):
		frappe.set_user(HR)
		try:
			return frappe.get_doc("Leave Change Request", name).decide(decision, "Talked on WhatsApp")
		finally:
			frappe.set_user("Administrator")

	def balance(self):
		return get_leave_balance_on(self.employee, LEAVE_TYPE, self.days[0])

	def test_cancel_after_hr_approves(self):
		leave = self.approved_leave(self.days[0])
		before = self.balance()

		# the checklist comes first: the employee must have told HR
		self.assertRaises(LeaveChangeRequestError, self.ask, leave, checklist=False)
		name = self.ask(leave)
		self.assertRaises(LeaveChangeRequestError, self.ask, leave)

		# nothing changes until HR decides
		self.assertEqual(frappe.db.get_value("Leave Application", leave.name, "docstatus"), 1)
		self.assertEqual(self.decide_as_hr(name, "Approved"), "Approved")
		self.assertEqual(frappe.db.get_value("Leave Application", leave.name, "docstatus"), 2)
		self.assertEqual(self.balance(), before + 1)

		request = frappe.get_doc("Leave Change Request", name)
		self.assertEqual((request.decided_by, request.hr_note), (HR, "Talked on WhatsApp"))
		self.assertTrue(
			frappe.db.exists("PWA Notification", {"to_user": STAFF, "reference_document_name": leave.name})
		)

	def test_new_dates_keep_the_approval(self):
		leave = self.approved_leave(self.days[0])
		new_date = str(self.days[1])
		notified = frappe.db.count("PWA Notification", {"to_user": HEAD})

		self.assertRaises(
			LeaveChangeRequestError,
			self.ask,
			leave,
			"Change the dates",
			new_from_date=str(self.days[0]),
			new_to_date=str(self.days[0]),
		)
		name = self.ask(leave, "Change the dates", new_from_date=new_date, new_to_date=new_date)
		self.decide_as_hr(name, "Approved")

		new_name = frappe.db.get_value("Leave Change Request", name, "new_leave_application")
		new = frappe.get_doc("Leave Application", new_name)
		self.assertEqual((new.docstatus, new.status, new.amended_from), (1, "Approved", leave.name))
		self.assertEqual(str(new.from_date), new_date)
		self.assertEqual([(r.approver, r.decision) for r in new.approvers], [(HEAD, "Approved")])
		self.assertEqual(frappe.db.get_value("Leave Application", leave.name, "docstatus"), 2)
		# the supervisor isn't asked again
		self.assertEqual(frappe.db.count("PWA Notification", {"to_user": HEAD}), notified)

		frappe.set_user(STAFF)
		try:
			rows = get_my_leave_changes(new_name)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual([r.name for r in rows], [name])

	def test_failed_change_leaves_everything_as_it_was(self):
		leave = self.approved_leave(self.days[0])
		self.approved_leave(self.days[2])
		day = str(self.days[2])
		name = self.ask(leave, "Change the dates", new_from_date=day, new_to_date=day)

		self.assertRaises(frappe.ValidationError, self.decide_as_hr, name, "Approved")
		self.assertEqual(frappe.db.get_value("Leave Application", leave.name, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Leave Change Request", name, "status"), "Open")

	def test_rejected_withdrawn_and_who_may_do_what(self):
		leave = self.approved_leave(self.days[0])
		name = self.ask(leave)

		# only HR decides, and only through Approve/Reject
		frappe.set_user(HEAD)
		try:
			self.assertRaises(frappe.PermissionError, frappe.get_doc("Leave Change Request", name).decide, "Approved")
		finally:
			frappe.set_user("Administrator")
		request = frappe.get_doc("Leave Change Request", name)
		request.status = "Approved"
		self.assertRaises(LeaveChangeRequestError, request.save)

		self.decide_as_hr(name, "Rejected")
		self.assertEqual(frappe.db.get_value("Leave Application", leave.name, "docstatus"), 1)
		self.assertRaises(LeaveChangeRequestError, self.decide_as_hr, name, "Approved")

		# a colleague can't ask about someone else's leave; the employee can take back an open request
		frappe.set_user(COLLEAGUE)
		try:
			self.assertRaises(
				frappe.PermissionError, request_leave_change, leave.name, "Cancel the leave", "x", 1, 1
			)
		finally:
			frappe.set_user("Administrator")
		name = self.ask(leave)
		frappe.set_user(STAFF)
		try:
			withdraw_leave_change(name)
		finally:
			frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Leave Change Request", name))

	def test_team_history_for_supervisors(self):
		leave = self.approved_leave(self.days[0])
		month_start = str(getdate().replace(day=1))
		today = str(getdate())

		frappe.set_user(HEAD)
		try:
			history = get_team_leave_history()
			self.assertIn(leave.name, [r.name for r in history["requests"]])
			self.assertEqual(
				{e["employee"] for e in history["employees"]}, {self.employee, self.colleague}
			)
			self.assertEqual(get_team_leave_history(employee=self.colleague)["requests"], [])
			self.assertEqual(get_team_leave_history(status="Rejected")["requests"], [])

			team = {row["employee"]: row for row in get_team_attendance(month_start, today)}
			self.assertEqual(set(team), {self.employee, self.colleague})
			self.assertEqual(
				set(team[self.employee]["counts"]), {"on_time", "late", "on_leave", "absent", "no_checkin"}
			)
			self.assertTrue(get_attendance_month(month_start, today, self.employee))
		finally:
			frappe.set_user("Administrator")

		frappe.set_user(OUTSIDER)
		try:
			self.assertEqual(get_team_leave_history()["requests"], [])
			self.assertEqual(get_team_attendance(month_start, today), [])
			self.assertRaises(frappe.PermissionError, get_attendance_month, month_start, today, self.employee)
		finally:
			frappe.set_user("Administrator")


def working_days(employee, count):
	"""The next `count` working days from a week ahead."""
	date = add_days(getdate(), 7)
	holidays = {str(d) for d in get_holiday_dates_for_employee(employee, date, add_days(date, 60))}
	days = []
	while len(days) < count:
		if str(date) not in holidays and date.weekday() < 5:
			days.append(date)
		date = add_days(date, 1)
	return days

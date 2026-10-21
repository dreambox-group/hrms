# Copyright (c) 2026, Dreambox and contributors
# See license.txt

import frappe
from frappe.utils import add_days, get_year_ending, get_year_start, getdate, nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.api import get_leave_applications
from hrms.hr.doctype.leave_application.leave_application import (
	LeaveApprovalError,
	get_leave_applications_waiting_for,
	get_leave_approvers,
	record_leave_decision,
)
from hrms.hr.doctype.leave_application.test_leave_application import make_allocation_record
from hrms.hr.utils import get_holiday_dates_for_employee
from hrms.tests.utils import HRMSTestSuite, make_user

COMPANY = "_Test Company"
VP = "la.vp@example.com"
HR = "la.hr@example.com"
HEAD = "la.finance.head@example.com"
SARI = "la.sari@example.com"
TONO = "la.tono@example.com"
RUDI = "la.rudi@example.com"


class TestLeaveApprovalLevels(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 1)
		delete_test_leave_applications()

		# Holding (VP, HR) ─┬─ Finance (Head; Sari, Tono)
		#                   └─ Design (Rudi only, no Required approver)
		self.holding = make_department(
			"_Test LA Holding", is_group=1, approvers=[(VP, "Required"), (HR, "Required")]
		)
		self.finance = make_department(
			"_Test LA Finance",
			parent=self.holding,
			approvers=[(HEAD, "Required"), (SARI, "Regular"), (TONO, "Regular")],
		)
		self.design = make_department("_Test LA Design", parent=self.holding, approvers=[(RUDI, "Regular")])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)

	def test_who_decides(self):
		staff = make_employee("la.staff@example.com", COMPANY, department=self.finance)
		self.assertEqual(
			approvers_of(staff),
			[
				(SARI, "Regular", self.finance),
				(TONO, "Regular", self.finance),
				(HEAD, "Required", self.finance),
			],
		)

		# a Regular approver's own leave goes to the department's Required approvers only
		self.assertEqual(
			approvers_of(make_employee(SARI, COMPANY, department=self.finance)),
			[(HEAD, "Required", self.finance)],
		)

		# a Required approver's own leave goes up to the parent department
		self.assertEqual(
			approvers_of(make_employee(HEAD, COMPANY, department=self.finance)),
			[(VP, "Required", self.holding), (HR, "Required", self.holding)],
		)

		# no Required approver in the department: the parent's Required approvers decide
		self.assertEqual(
			approvers_of(make_employee("la.designer@example.com", COMPANY, department=self.design)),
			[(RUDI, "Regular", self.design), (VP, "Required", self.holding), (HR, "Required", self.holding)],
		)

		# nobody above the top department
		vp = make_employee(VP, COMPANY, department=self.holding)
		self.assertRaises(LeaveApprovalError, get_leave_approvers, vp)

	def test_required_and_regular_approval_needed(self):
		application = apply_for_leave(
			make_employee("la.designer@example.com", COMPANY, department=self.design)
		)

		# everyone is notified, Regular and Required
		for user in (RUDI, VP, HR):
			self.assertTrue(
				frappe.db.exists(
					"PWA Notification", {"to_user": user, "reference_document_name": application.name}
				)
			)

		self.assertEqual(decide(application, VP, "Approved"), "Open")
		# all Required approvers approved, but no Regular approver yet
		self.assertEqual(decide(application, HR, "Approved"), "Open")
		self.assertEqual(decide(application, RUDI, "Approved"), "Approved")

		application.reload()
		self.assertEqual(application.docstatus, 1)
		self.assertEqual(application.status, "Approved")
		self.assertEqual(
			[(row.approver, row.decision) for row in application.approvers],
			[(RUDI, "Approved"), (VP, "Approved"), (HR, "Approved")],
		)

	def test_required_rejection_rejects(self):
		application = apply_for_leave(make_employee("la.staff@example.com", COMPANY, department=self.finance))

		self.assertEqual(decide(application, SARI, "Approved"), "Open")
		self.assertEqual(decide(application, HEAD, "Rejected"), "Rejected")

		application.reload()
		self.assertEqual(application.docstatus, 1)
		self.assertEqual(application.status, "Rejected")

	def test_regular_rejection_rejects(self):
		application = apply_for_leave(
			make_employee("la.designer@example.com", COMPANY, department=self.design)
		)

		self.assertEqual(decide(application, VP, "Approved"), "Open")
		self.assertEqual(decide(application, RUDI, "Rejected"), "Rejected")
		self.assertEqual(frappe.db.get_value("Leave Application", application.name, "docstatus"), 1)

	def test_no_regular_approver_needed_when_there_is_none(self):
		# a Regular approver's own leave only has Required approvers
		application = apply_for_leave(make_employee(SARI, COMPANY, department=self.finance))

		self.assertEqual(decide(application, HEAD, "Approved"), "Approved")

	def test_regular_approvers_decide_as_a_group(self):
		application = apply_for_leave(make_employee("la.staff@example.com", COMPANY, department=self.finance))
		for user in (SARI, TONO, HEAD):
			self.assertIn(application.name, get_leave_applications_waiting_for(user))
		self.assertIn(application.name, approval_list_of(SARI))

		decide(application, SARI, "Approved")

		# the other Regular approver no longer has it to decide, but can still see it
		self.assertNotIn(application.name, get_leave_applications_waiting_for(TONO))
		self.assertNotIn(application.name, approval_list_of(TONO))
		self.assertRaises(LeaveApprovalError, decide, application, TONO, "Rejected")
		self.assertTrue(frappe.has_permission("Leave Application", "read", doc=application.name, user=TONO))

		# the Required approver still decides
		self.assertIn(application.name, get_leave_applications_waiting_for(HEAD))

	def test_decisions_are_final_and_only_approvers_decide(self):
		application = apply_for_leave(
			make_employee("la.designer@example.com", COMPANY, department=self.design)
		)

		decide(application, VP, "Approved")
		self.assertRaises(LeaveApprovalError, decide, application, VP, "Rejected")
		self.assertRaises(frappe.PermissionError, decide, application, SARI, "Approved")

	def test_status_cannot_skip_the_approvers(self):
		application = apply_for_leave(make_employee("la.staff@example.com", COMPANY, department=self.finance))

		application.status = "Approved"
		self.assertRaises(LeaveApprovalError, application.submit)

		# decisions come from the database, not from the submitted rows
		application.reload()
		for row in application.approvers:
			row.decision = "Approved"
		application.status = "Approved"
		self.assertRaises(LeaveApprovalError, application.submit)

	def test_replacing_an_approver_moves_open_requests(self):
		application = apply_for_leave(make_employee("la.staff@example.com", COMPANY, department=self.finance))
		new_head = make_user("la.finance.newhead@example.com", "Employee")

		finance = frappe.get_doc("Department", self.finance)
		for row in finance.leave_approvers:
			if row.approver == HEAD:
				row.approver = new_head
		finance.save()

		application.reload()
		self.assertIn((new_head, "Required", "Pending"), approver_rows(application))
		self.assertNotIn(HEAD, [row.approver for row in application.approvers])
		self.assertIn(application.name, get_leave_applications_waiting_for(new_head))

		decide(application, SARI, "Approved")
		self.assertEqual(decide(application, new_head, "Approved"), "Approved")

	def test_removing_the_last_pending_approver_completes_the_request(self):
		application = apply_for_leave(
			make_employee("la.designer@example.com", COMPANY, department=self.design)
		)
		decide(application, VP, "Approved")
		decide(application, RUDI, "Approved")

		holding = frappe.get_doc("Department", self.holding)
		holding.leave_approvers = [row for row in holding.leave_approvers if row.approver != HR]
		holding.save()

		application.reload()
		self.assertEqual(application.docstatus, 1)
		self.assertEqual(application.status, "Approved")

	def test_stock_approver_when_disabled(self):
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)
		employee = make_employee("la.staff@example.com", COMPANY, department=self.finance)
		application = apply_for_leave(employee, leave_approver=SARI)

		self.assertEqual(application.leave_approver, SARI)
		self.assertFalse(application.approvers)


def delete_test_leave_applications():
	employees = frappe.get_all("Employee", filters={"user_id": ("like", "la.%@example.com")}, pluck="name")
	if not employees:
		return

	applications = frappe.get_all("Leave Application", filters={"employee": ("in", employees)}, pluck="name")
	if applications:
		frappe.db.delete("Leave Application Approver", {"parent": ("in", applications)})
		frappe.db.delete("Leave Application", {"name": ("in", applications)})
	frappe.db.delete(
		"Leave Ledger Entry", {"employee": ("in", employees), "transaction_type": "Leave Application"}
	)


def make_department(name, parent="All Departments", is_group=0, approvers=()):
	department = frappe.db.get_value("Department", {"department_name": name, "company": COMPANY})
	department = (
		frappe.get_doc("Department", department)
		if department
		else frappe.get_doc({"doctype": "Department", "department_name": name, "company": COMPANY})
	)
	department.parent_department = parent
	department.is_group = is_group
	department.leave_approvers = []
	for user, level in approvers:
		make_user(user, "Employee")
		department.append("leave_approvers", {"approver": user, "approval_level": level})
	department.save()
	return department.name


def apply_for_leave(employee, leave_approver=None):
	date = get_working_day(employee)
	if not frappe.db.exists(
		"Leave Allocation",
		{"employee": employee, "leave_type": "_Test Leave Type", "docstatus": 1, "to_date": (">=", date)},
	):
		make_allocation_record(employee, from_date=get_year_start(date), to_date=get_year_ending(date))

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


def get_working_day(employee):
	date = add_days(getdate(), 7)
	holidays = {str(d) for d in get_holiday_dates_for_employee(employee, date, get_year_ending(date))}
	while str(date) in holidays or date.weekday() >= 5:
		date = add_days(date, 1)
	return date


def decide(application, user, decision):
	frappe.set_user(user)
	try:
		return record_leave_decision(application.name, decision)
	finally:
		frappe.set_user("Administrator")


def approval_list_of(user):
	frappe.set_user(user)
	try:
		return [d.name for d in get_leave_applications(employee="", approver_id=user, for_approval=True)]
	finally:
		frappe.set_user("Administrator")


def approvers_of(employee):
	return [(a.approver, a.approval_level, a.department) for a in get_leave_approvers(employee)]


def approver_rows(application):
	return [(row.approver, row.approval_level, row.decision) for row in application.approvers]

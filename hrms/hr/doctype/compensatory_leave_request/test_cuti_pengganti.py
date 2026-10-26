# Copyright (c) 2026, Dreambox and contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.utils import add_days, add_months, getdate, nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.api.employee_app import decide_cuti_pengganti, get_my_cuti_pengganti, request_cuti_pengganti
from hrms.hr.doctype.compensatory_leave_request.cuti_pengganti import (
	CutiPenggantiError,
	expire_unused,
	get_requests_waiting_for,
)
from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
from hrms.hr.doctype.leave_application.test_leave_approval_levels import make_department
from hrms.hr.utils import get_holiday_dates_for_employee
from hrms.tests.utils import HRMSTestSuite

COMPANY = "_Test Company"
CUTI = "_Test Cuti Pengganti"
STAFF = "cp.staff@example.com"
HEAD = "cp.head@example.com"
LEAD = "cp.lead@example.com"
LEAD2 = "cp.lead2@example.com"
TODAY = "hrms.hr.doctype.compensatory_leave_request.cuti_pengganti.today"


class TestCutiPengganti(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Leave Type", CUTI):
			frappe.get_doc({"doctype": "Leave Type", "leave_type_name": CUTI, "is_compensatory": 1}).insert()
		frappe.db.set_single_value("HR Settings", "compensatory_leave_type", CUTI)
		frappe.db.set_single_value("HR Settings", "compensatory_leave_expiry_months", 3)
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 1)
		department = make_department(
			"_Test CP Team", approvers=[(HEAD, "Required"), (LEAD, "Regular"), (LEAD2, "Regular")]
		)
		self.employee = make_employee(STAFF, COMPANY, department=department)
		frappe.db.set_value("Employee", self.employee, "employment_type", None)
		requests = frappe.get_all("Compensatory Leave Request", filters={"employee": self.employee}, pluck="name")
		frappe.db.delete("Leave Application Approver", {"parent": ("in", requests or [""])})
		for doctype in ("Compensatory Leave Request", "Leave Application", "Leave Ledger Entry", "Leave Allocation"):
			frappe.db.delete(doctype, {"employee": self.employee})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "compensatory_leave_type", None)
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)

	def request(self, days_ago, reason="Weekend event"):
		frappe.set_user(STAFF)
		try:
			return request_cuti_pengganti(str(add_days(getdate(), -days_ago)), reason)
		finally:
			frappe.set_user("Administrator")

	def decide(self, name, user, decision):
		frappe.set_user(user)
		try:
			return decide_cuti_pengganti(name, decision)
		finally:
			frappe.set_user("Administrator")

	def approve_as_hr(self, name):
		doc = frappe.get_doc("Compensatory Leave Request", name)
		doc.status = "Approved"
		doc.submit()
		return doc

	def balance(self, date=None):
		return get_leave_balance_on(self.employee, CUTI, date or getdate())

	def test_supervisors_approve_like_leave(self):
		name = self.request(3)
		doc = frappe.get_doc("Compensatory Leave Request", name)
		self.assertEqual(doc.status, "Open")
		self.assertEqual(doc.leave_type, CUTI)
		self.assertEqual(getdate(doc.expires_on), add_months(add_days(getdate(), -3), 3))
		self.assertEqual({r.approver for r in doc.approvers}, {HEAD, LEAD, LEAD2})
		self.assertEqual([r.name for r in get_requests_waiting_for(LEAD)], [name])

		# one Regular supervisor decides for the group; the Required one is still needed
		self.assertEqual(self.decide(name, LEAD, "Approved"), "Open")
		self.assertEqual(get_requests_waiting_for(LEAD2), [])
		self.assertRaises(CutiPenggantiError, self.decide, name, LEAD2, "Approved")
		self.assertEqual(self.balance(), 0)

		self.assertEqual(self.decide(name, HEAD, "Approved"), "Approved")
		doc.reload()
		self.assertEqual(doc.docstatus, 1)
		self.assertTrue(doc.leave_allocation)
		self.assertEqual(self.balance(), 1)

		# a second request goes onto the same allocation
		second = self.request(1)
		self.decide(second, LEAD2, "Approved")
		self.decide(second, HEAD, "Approved")
		self.assertEqual(frappe.db.get_value("Compensatory Leave Request", second, "leave_allocation"), doc.leave_allocation)
		self.assertEqual(self.balance(), 2)

	def test_anyone_rejecting_rejects(self):
		name = self.request(2)
		self.assertEqual(self.decide(name, LEAD, "Rejected"), "Rejected")
		doc = frappe.get_doc("Compensatory Leave Request", name)
		self.assertEqual(doc.docstatus, 1)
		self.assertFalse(doc.leave_allocation)
		self.assertEqual(self.balance(), 0)

	def test_only_supervisors_or_hr_decide(self):
		name = self.request(2)
		# the employee can't approve their own request by editing it
		frappe.set_user(STAFF)
		try:
			doc = frappe.get_doc("Compensatory Leave Request", name)
			doc.status = "Approved"
			doc.save()
			self.assertEqual(doc.status, "Open")
			self.assertRaises(frappe.PermissionError, decide_cuti_pengganti, name, "Approved")
		finally:
			frappe.set_user("Administrator")
		# HR can decide in the desk
		self.assertTrue(self.approve_as_hr(name).leave_allocation)
		self.assertEqual(self.balance(), 1)

	def test_rules_for_the_day(self):
		frappe.set_user(STAFF)
		try:
			self.assertRaises(frappe.ValidationError, request_cuti_pengganti, str(add_days(getdate(), 1)), "Later")
		finally:
			frappe.set_user("Administrator")
		# overtime on a working day counts too: no holiday or attendance needed
		name = self.request(0)
		self.assertTrue(name)
		# a day whose days already expired can't be approved
		old = self.request(100)
		self.assertRaises(CutiPenggantiError, self.decide, old, HEAD, "Approved")

	def test_each_request_expires_on_its_own(self):
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)
		first = self.approve_as_hr(self.request(20))
		second = self.approve_as_hr(self.request(5))
		self.assertEqual(self.balance(), 2)

		# one day taken: it uses the request that expires first
		leave = take_leave(self.employee, next_working_day(self.employee, add_days(getdate(), 3)))
		after_first = add_days(first.expires_on, 1)
		with patch(TODAY, return_value=str(after_first)):
			expire_unused(self.employee)
		self.assertEqual(frappe.db.get_value("Compensatory Leave Request", first.name, "expired_leaves"), 0)
		self.assertEqual(self.balance(after_first), 1)

		after_second = add_days(second.expires_on, 1)
		with patch(TODAY, return_value=str(after_second)):
			expire_unused(self.employee)
		self.assertEqual(frappe.db.get_value("Compensatory Leave Request", second.name, "expired_leaves"), 1)
		self.assertEqual(self.balance(after_second), 0)

		# leave cancelled after both expired: the first request's day expires too
		leave.cancel()
		with patch(TODAY, return_value=str(after_second)):
			expire_unused(self.employee)
		self.assertEqual(frappe.db.get_value("Compensatory Leave Request", first.name, "expired_leaves"), 1)
		self.assertEqual(self.balance(after_second), 0)
		self.assertEqual(self.balance(), 2)

	def test_leave_must_fit_days_not_yet_expired(self):
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)
		credit = self.approve_as_hr(self.request(10))
		late = next_working_day(self.employee, add_days(credit.expires_on, 1))
		self.assertRaises(CutiPenggantiError, take_leave, self.employee, late, submit=False)
		take_leave(self.employee, next_working_day(self.employee, add_days(getdate(), 3)), submit=False)

	def test_employee_app_summary(self):
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)
		approved = self.approve_as_hr(self.request(10))
		open_request = self.request(2)
		frappe.set_user(STAFF)
		try:
			summary = get_my_cuti_pengganti()
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(summary["enabled"])
		self.assertEqual(summary["available"], 1)
		self.assertEqual(getdate(summary["next_expiry"]["date"]), getdate(approved.expires_on))
		by_name = {r.name: r for r in summary["requests"]}
		self.assertEqual(by_name[approved.name].left, 1)
		self.assertEqual(by_name[open_request].status, "Open")


def next_working_day(employee, date):
	date = getdate(date)
	holidays = {getdate(d) for d in get_holiday_dates_for_employee(employee, date, add_days(date, 30))}
	while date in holidays or date.weekday() >= 5:
		date = add_days(date, 1)
	return date


def take_leave(employee, date, submit=True):
	leave = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": CUTI,
			"from_date": date,
			"to_date": date,
			"company": COMPANY,
			"posting_date": nowdate(),
		}
	).insert()
	if submit:
		leave.status = "Approved"
		leave.submit()
	return leave

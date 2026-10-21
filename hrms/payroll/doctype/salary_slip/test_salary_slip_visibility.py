# Copyright (c) 2026, Dreambox and contributors
# See license.txt

import frappe

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.payroll.doctype.salary_slip.test_salary_slip import make_employee_salary_slip
from hrms.tests.utils import HRMSTestSuite, make_user

COMPANY = "_Test Company"
STAFF = "slipview.staff@example.com"
HEAD = "slipview.head@example.com"
PAYROLL = "slipview.payroll@example.com"


class TestSalarySlipVisibility(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		self.staff = make_employee(STAFF, COMPANY)
		self.head = make_employee(HEAD, COMPANY)
		# a department head: approves leave, but isn't payroll staff
		make_user(HEAD, "Leave Approver")
		make_user(PAYROLL, "HR User")
		self.staff_slip = make_employee_salary_slip(self.staff, "Monthly").name
		self.head_slip = make_employee_salary_slip(self.head, "Monthly").name

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_everyone_sees_only_their_own_slips(self):
		for user, own, other in (
			(STAFF, self.staff_slip, self.head_slip),
			(HEAD, self.head_slip, self.staff_slip),
		):
			frappe.set_user(user)
			visible = frappe.get_list("Salary Slip", pluck="name")
			self.assertIn(own, visible)
			self.assertNotIn(other, visible)

			self.assertTrue(frappe.has_permission("Salary Slip", "read", doc=own))
			self.assertFalse(frappe.has_permission("Salary Slip", "read", doc=other))
			self.assertRaises(
				frappe.PermissionError, frappe.get_doc("Salary Slip", other).check_permission, "read"
			)

	def test_payroll_staff_see_all_slips(self):
		frappe.set_user(PAYROLL)
		visible = frappe.get_list("Salary Slip", pluck="name", limit=0)
		self.assertIn(self.staff_slip, visible)
		self.assertIn(self.head_slip, visible)

	def test_login_without_an_employee_sees_none(self):
		make_user("slipview.nobody@example.com", "Employee")
		frappe.set_user("slipview.nobody@example.com")
		try:
			visible = frappe.get_list("Salary Slip", pluck="name")
		except frappe.PermissionError:
			visible = []
		self.assertEqual(visible, [])

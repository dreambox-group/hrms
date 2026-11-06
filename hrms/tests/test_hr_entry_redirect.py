# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""/hr for a signed-in account without an employee record: desk accounts go to the desk."""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.www.hrms import HR_DESK_ROUTE, redirect_desk_user_without_employee

DESK_ONLY = "_test_desk_only_user@example.com"
EMPLOYEE_USER = "_test_hr_entry_employee@example.com"
OTHER_DESK = "_test_other_desk_user@example.com"


class TestHrEntryRedirect(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("User", DESK_ONLY):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": DESK_ONLY,
					"first_name": "Desk Only",
					"send_welcome_email": 0,
					"roles": [{"role": "HR Manager"}],
				}
			).insert(ignore_permissions=True)
		make_employee(EMPLOYEE_USER, company=frappe.get_all("Company", limit=1, pluck="name")[0])

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_guest_is_left_alone(self):
		frappe.set_user("Guest")
		redirect_desk_user_without_employee()

	def test_hr_desk_account_without_employee_goes_to_hr_desk(self):
		for user in ("Administrator", DESK_ONLY):
			frappe.set_user(user)
			with self.assertRaises(frappe.Redirect):
				redirect_desk_user_without_employee()
			self.assertEqual(frappe.local.flags.redirect_location, HR_DESK_ROUTE)

	def test_other_desk_account_without_employee_goes_to_desk(self):
		if not frappe.db.exists("User", OTHER_DESK):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": OTHER_DESK,
					"first_name": "Other Desk",
					"send_welcome_email": 0,
					"roles": [{"role": "Accounts User"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(OTHER_DESK)
		with self.assertRaises(frappe.Redirect):
			redirect_desk_user_without_employee()
		self.assertEqual(frappe.local.flags.redirect_location, "/desk")

	def test_employee_stays_in_the_app(self):
		frappe.set_user(EMPLOYEE_USER)
		redirect_desk_user_without_employee()

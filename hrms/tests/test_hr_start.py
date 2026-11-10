# Copyright (c) 2026, Dreambox and contributors
# See license.txt

"""Production HRIS for HR (owner, 10 Nov 2026): HR lands on /hr-start (two buttons), and the
ERPNext tile is left off the desk's apps screen for anyone without an ERPNext role."""

import frappe

from hrms.patches.v16_0 import hr_start_home_page
from hrms.tests.utils import HRMSTestSuite
from hrms.utils import hide_erpnext_tile_from_hr

HR = "hr.start.test@example.com"
ACCOUNTS = "accounts.start.test@example.com"


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		)
		for role in roles:
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
	return email


def boot():
	return frappe._dict(app_data=[{"app_name": "erpnext", "on_apps_screen": True}, {"app_name": "hrms", "on_apps_screen": True}])


class TestHRStart(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		make_user(HR, ["HR User", "HR Manager"])
		make_user(ACCOUNTS, ["HR User", "Accounts User"])

	def tearDown(self):
		frappe.set_user("Administrator")

	def shown(self, user):
		frappe.set_user(user)
		bootinfo = boot()
		hide_erpnext_tile_from_hr(bootinfo)
		frappe.set_user("Administrator")
		return {a["app_name"] for a in bootinfo.app_data if a["on_apps_screen"]}

	def test_erpnext_tile_hidden_from_hr_only(self):
		self.assertEqual(self.shown(HR), {"hrms"})

	def test_erpnext_tile_kept_for_an_erpnext_role_and_administrator(self):
		self.assertEqual(self.shown(ACCOUNTS), {"erpnext", "hrms"})
		self.assertEqual(self.shown("Administrator"), {"erpnext", "hrms"})

	def test_patch_sets_hr_home_page_only_where_empty(self):
		frappe.db.set_value("Role", "HR User", "home_page", "")
		frappe.db.set_value("Role", "HR Manager", "home_page", "/desk/somewhere")
		hr_start_home_page.execute()
		self.assertEqual(frappe.db.get_value("Role", "HR User", "home_page"), "hr-start")
		self.assertEqual(frappe.db.get_value("Role", "HR Manager", "home_page"), "/desk/somewhere")

	def test_page_sends_others_to_drea_one_and_guests_to_sign_in(self):
		from hrms.www import hr_start

		for user, where in (("Guest", "/login?redirect-to=%2Fhr-start"), (ACCOUNTS, None), (HR, None)):
			frappe.set_user(user)
			frappe.local.flags.redirect_location = None
			try:
				hr_start.get_context(frappe._dict())
				self.assertIsNone(where, user)
			except frappe.Redirect:
				self.assertEqual(frappe.local.flags.redirect_location, where, user)
		frappe.set_user("Administrator")
		plain = make_user("plain.start.test@example.com", [])
		frappe.set_user(plain)
		with self.assertRaises(frappe.Redirect):
			hr_start.get_context(frappe._dict())
		self.assertEqual(frappe.local.flags.redirect_location, "/hr")

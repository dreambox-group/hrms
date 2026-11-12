# Copyright (c) 2026, Dreambox and contributors
# See license.txt

"""Two addresses, one site (owner, 11 Nov 2026): hris.dreambox.id is HR only, one.dreambox.id is
for everyone (hrms.utils.drea_doors); HR's home page is HR Setup (patch hr_home_page_desk); the
ERPNext tile stays off the apps screen for anyone without an ERPNext role (hrms.utils)."""

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from hrms.patches.v16_0 import hr_home_page_desk
from hrms.tests.utils import HRMSTestSuite
from hrms.utils import drea_doors, hide_erpnext_tile_from_hr

HR = "hr.doors.test@example.com"
STAFF = "staff.doors.test@example.com"
ACCOUNTS = "accounts.doors.test@example.com"
HR_HOST = "hris.example.test"
STAFF_HOST = "one.example.test"


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		)
		for role in roles:
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
	return email


class FakeLoginManager:
	def __init__(self, user=None):
		self.user = user
		self.logged_out = False

	def logout(self):
		self.logged_out = True


class TestDreaDoors(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		make_user(HR, ["HR User", "HR Manager"])
		make_user(STAFF, ["Employee"])
		make_user(ACCOUNTS, ["HR User", "Accounts User"])
		self._conf = {k: frappe.conf.get(k) for k in ("drea_hr_host", "drea_staff_host")}
		self._request = getattr(frappe.local, "request", None)
		self._login_manager = getattr(frappe.local, "login_manager", None)
		frappe.conf.drea_hr_host = HR_HOST
		frappe.conf.drea_staff_host = STAFF_HOST

	def tearDown(self):
		for k, v in self._conf.items():
			frappe.conf[k] = v
		frappe.local.request = self._request
		frappe.local.login_manager = self._login_manager
		frappe.set_user("Administrator")

	def arrive_on(self, host):
		headers = {"X-Forwarded-Host": host} if host else {}
		frappe.local.request = Request(EnvironBuilder(path="/api/method/login", headers=headers).get_environ())

	# --- signing in -------------------------------------------------------------------------

	def test_hr_address_refuses_staff_and_lets_hr_in(self):
		self.arrive_on(HR_HOST)
		with self.assertRaises(frappe.AuthenticationError) as refused:
			drea_doors.refuse_non_hr_sign_in(FakeLoginManager(STAFF))
		self.assertIn(STAFF_HOST, str(refused.exception))
		for user in (HR, ACCOUNTS, "Administrator", "Guest"):
			drea_doors.refuse_non_hr_sign_in(FakeLoginManager(user))  # no error (Guest: signing out)

	def test_staff_address_lets_everyone_in(self):
		self.arrive_on(STAFF_HOST)
		for user in (STAFF, HR, "Administrator"):
			drea_doors.refuse_non_hr_sign_in(FakeLoginManager(user))

	def test_nothing_is_refused_without_the_label_or_the_setting(self):
		self.arrive_on(None)  # no X-Forwarded-Host: never refuse, so staff are never locked out
		drea_doors.refuse_non_hr_sign_in(FakeLoginManager(STAFF))
		self.arrive_on(HR_HOST)
		frappe.conf.drea_hr_host = None  # a site that has not opted in
		drea_doors.refuse_non_hr_sign_in(FakeLoginManager(STAFF))

	def test_host_label_is_read_case_and_port_blind(self):
		self.arrive_on("HRIS.Example.Test:443, proxy.internal")
		with self.assertRaises(frappe.AuthenticationError):
			drea_doors.refuse_non_hr_sign_in(FakeLoginManager(STAFF))

	# --- a session that already exists ----------------------------------------------------

	def test_old_staff_session_on_hr_address_is_ended(self):
		self.arrive_on(HR_HOST)
		frappe.local.login_manager = FakeLoginManager()
		frappe.set_user(STAFF)
		with self.assertRaises(frappe.AuthenticationError):
			drea_doors.end_non_hr_session()
		self.assertTrue(frappe.local.login_manager.logged_out)

	def test_hr_session_and_staff_on_staff_address_carry_on(self):
		frappe.local.login_manager = FakeLoginManager()
		self.arrive_on(HR_HOST)
		frappe.set_user(HR)
		drea_doors.end_non_hr_session()
		self.arrive_on(STAFF_HOST)
		frappe.set_user(STAFF)
		drea_doors.end_non_hr_session()
		frappe.set_user("Guest")
		self.arrive_on(HR_HOST)
		drea_doors.end_non_hr_session()  # guests reach the sign-in page
		self.assertFalse(frappe.local.login_manager.logged_out)

	# --- HR's home page and the apps screen -----------------------------------------------

	def test_hr_home_page_is_hr_setup_where_empty_or_the_old_page(self):
		before = {r: frappe.db.get_value("Role", r, "home_page") for r in ("HR User", "HR Manager")}
		try:
			frappe.db.set_value("Role", "HR User", "home_page", "hr-start")
			frappe.db.set_value("Role", "HR Manager", "home_page", "/desk/somewhere")
			hr_home_page_desk.execute()
			self.assertEqual(frappe.db.get_value("Role", "HR User", "home_page"), "desk/hr-setup")
			self.assertEqual(frappe.db.get_value("Role", "HR Manager", "home_page"), "/desk/somewhere")
			frappe.db.set_value("Role", "HR Manager", "home_page", "")
			hr_home_page_desk.execute()
			self.assertEqual(frappe.db.get_value("Role", "HR Manager", "home_page"), "desk/hr-setup")
		finally:
			for role, page in before.items():
				frappe.db.set_value("Role", role, "home_page", page)
			frappe.cache.delete_key("home_page")

	def test_hr_home_page_moves_to_hr_dashboard_unless_chosen(self):
		from hrms.patches.v16_0 import hr_home_page_dashboard

		before = {r: frappe.db.get_value("Role", r, "home_page") for r in ("HR User", "HR Manager")}
		try:
			frappe.db.set_value("Role", "HR User", "home_page", "desk/hr-setup")
			frappe.db.set_value("Role", "HR Manager", "home_page", "/desk/somewhere")
			hr_home_page_dashboard.execute()
			self.assertEqual(frappe.db.get_value("Role", "HR User", "home_page"), "desk/hr-dashboard")
			self.assertEqual(frappe.db.get_value("Role", "HR Manager", "home_page"), "/desk/somewhere")
		finally:
			for role, page in before.items():
				frappe.db.set_value("Role", role, "home_page", page)
			frappe.cache.delete_key("home_page")

	def shown(self, user):
		frappe.set_user(user)
		bootinfo = frappe._dict(
			app_data=[{"app_name": "erpnext", "on_apps_screen": True}, {"app_name": "hrms", "on_apps_screen": True}]
		)
		hide_erpnext_tile_from_hr(bootinfo)
		frappe.set_user("Administrator")
		return {a["app_name"] for a in bootinfo.app_data if a["on_apps_screen"]}

	def test_erpnext_tile_hidden_from_hr_only(self):
		self.assertEqual(self.shown(HR), {"hrms"})
		self.assertEqual(self.shown(ACCOUNTS), {"erpnext", "hrms"})
		self.assertEqual(self.shown("Administrator"), {"erpnext", "hrms"})

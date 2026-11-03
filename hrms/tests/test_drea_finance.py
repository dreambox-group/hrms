# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""The Frappe side of Drea Finance in the same database (hrms.finance, hrms.setup.setup_drea_finance)."""

import frappe
from frappe.tests import IntegrationTestCase

from hrms.finance import finance_tables_using, has_finance_access, referencing_foreign_keys
from hrms.setup import DREA_FINANCE_PERMLEVEL_PERMS, get_drea_finance_custom_fields, setup_drea_finance

TEST_USER = "_test_finance_user@example.com"


class TestDreaFinanceSetup(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_drea_finance()

	def test_custom_fields_exist(self):
		for doctype, fields in get_drea_finance_custom_fields().items():
			for field in fields:
				self.assertTrue(
					frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}),
					f"{doctype}.{field['fieldname']} missing",
				)
		meta = frappe.get_meta("User")
		self.assertEqual(meta.get_field("drea_finance_role").permlevel, 1)
		self.assertEqual(meta.get_field("drea_finance_divisions").options, "User Division")
		self.assertTrue(frappe.get_meta("Company").get_field("drea_finance_code").unique)
		self.assertEqual(frappe.get_meta("Department").get_field("drea_finance_division").options, "Division")

	def test_role_and_permlevel_rights(self):
		self.assertTrue(frappe.db.exists("Role", "Finance Admin"))
		for doctype, roles in DREA_FINANCE_PERMLEVEL_PERMS.items():
			perms = {
				p.role: p
				for p in frappe.get_all(
					"Custom DocPerm",
					filters={"parent": doctype, "permlevel": 1},
					fields=["role", "read", "write"],
				)
			}
			for role, can_write in roles:
				self.assertIn(role, perms, f"{doctype} permlevel 1 for {role}")
				self.assertEqual(perms[role].read, 1)
				self.assertEqual(perms[role].write, 1 if can_write else 0)

	def test_setup_is_idempotent(self):
		setup_drea_finance()
		setup_drea_finance()
		self.assertEqual(
			frappe.db.count("Custom DocPerm", {"parent": "Company", "permlevel": 1, "role": "Finance Admin"}),
			1,
		)


class TestFinanceAccess(IntegrationTestCase):
	def setUp(self):
		setup_drea_finance()
		if not frappe.db.exists("User", TEST_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": TEST_USER,
					"first_name": "Finance Test",
					"send_welcome_email": 0,
					"roles": [{"role": "Employee"}],
				}
			).insert(ignore_permissions=True)
		self.old_url = frappe.db.get_single_value("HR Settings", "drea_finance_url")
		frappe.db.set_single_value("HR Settings", "drea_finance_url", "https://finance.example.com/")
		frappe.db.set_value("User", TEST_USER, {"drea_finance_role": None, "drea_finance_active": 1})

	def tearDown(self):
		frappe.db.set_single_value("HR Settings", "drea_finance_url", self.old_url)
		frappe.set_user("Administrator")

	def test_apps_screen_entry_needs_a_role_and_a_url(self):
		self.assertFalse(has_finance_access(TEST_USER))
		frappe.db.set_value("User", TEST_USER, "drea_finance_role", "staff")
		self.assertTrue(has_finance_access(TEST_USER))
		frappe.db.set_value("User", TEST_USER, "drea_finance_active", 0)
		self.assertFalse(has_finance_access(TEST_USER))
		frappe.db.set_value("User", TEST_USER, "drea_finance_active", 1)
		frappe.db.set_single_value("HR Settings", "drea_finance_url", "")
		self.assertFalse(has_finance_access(TEST_USER))
		self.assertFalse(has_finance_access("Guest"))

	def test_divisions_need_a_role(self):
		division = frappe.get_doc({"doctype": "Division", "division_name": "_Test Access Division"}).insert(
			ignore_if_duplicate=True
		)
		user = frappe.get_doc("User", TEST_USER)
		user.drea_finance_role = None
		user.append("drea_finance_divisions", {"division": division.name})
		self.assertRaises(frappe.ValidationError, user.save)
		# a failed save leaves the in-memory timestamp ahead of the database; start again from the database
		user.reload()
		user.drea_finance_role = "dept_head"
		user.append("drea_finance_divisions", {"division": division.name})
		user.save()
		self.assertEqual(frappe.db.count("User Division", {"parent": TEST_USER}), 1)

	def test_bad_role_refused(self):
		user = frappe.get_doc("User", TEST_USER)
		user.drea_finance_role = "owner"
		self.assertRaises(frappe.ValidationError, user.save)


class TestDeleteGuard(IntegrationTestCase):
	"""Finance's tables point at tabUser / tabCompany / tabDivision with foreign keys. The guard
	reads them from the catalog, so a throwaway table with a foreign key stands in for Finance."""

	TABLE = "_test_finance_rows"

	def setUp(self):
		if frappe.db.db_type != "postgres":
			self.skipTest("foreign keys are read from the Postgres catalog")
		if not frappe.db.exists("User", TEST_USER):
			frappe.get_doc(
				{"doctype": "User", "email": TEST_USER, "first_name": "Finance Test", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		frappe.db.sql(f'drop table if exists "{self.TABLE}"')
		frappe.db.sql(
			f'create table "{self.TABLE}" (id serial primary key, '
			f'requester varchar(140) references "tabUser"(name) on update cascade)'
		)

	def tearDown(self):
		frappe.db.sql(f'drop table if exists "{self.TABLE}"')

	def test_guard_sees_the_foreign_key_and_refuses_only_while_rows_exist(self):
		self.assertIn((self.TABLE, "requester"), referencing_foreign_keys("User"))
		self.assertEqual(finance_tables_using("User", TEST_USER), [])

		frappe.db.sql(f'insert into "{self.TABLE}" (requester) values (%s)', TEST_USER)
		self.assertEqual(finance_tables_using("User", TEST_USER), [self.TABLE])
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("User", TEST_USER)
		self.assertTrue(frappe.db.exists("User", TEST_USER))

		frappe.db.sql(f'delete from "{self.TABLE}"')
		frappe.delete_doc("User", TEST_USER)
		self.assertFalse(frappe.db.exists("User", TEST_USER))

	def test_nothing_to_check_on_a_table_without_foreign_keys(self):
		self.assertEqual(finance_tables_using("Division", "DV-99999"), [])

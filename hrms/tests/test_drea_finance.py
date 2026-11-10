# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""The Frappe side of Drea Finance in the same database (hrms.finance, hrms.setup.setup_drea_finance)."""

from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase

from hrms.finance import (
	NO_PASSWORD_DEFAULT,
	NO_PASSWORD_FIELD,
	finance_tables_using,
	has_finance_access,
	no_password_users,
	referencing_foreign_keys,
	refuse_service_account_login,
)
from hrms.setup import (
	DREA_FINANCE_PERMLEVEL_PERMS,
	DREA_FINANCE_RETIRED_FIELDS,
	fill_no_password_users,
	get_drea_finance_custom_fields,
	setup_drea_finance,
)

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
		# the Finance fields form their own tab at the end of the User form
		self.assertEqual(meta.get_field("drea_finance_section").fieldtype, "Tab Break")
		order = [f.fieldname for f in meta.fields]
		self.assertGreater(order.index("drea_finance_section"), order.index("active_sessions"))
		for doctype, fieldname in DREA_FINANCE_RETIRED_FIELDS:
			self.assertFalse(
				frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}),
				f"{doctype}.{fieldname} should be gone",
			)
			self.assertIsNone(frappe.get_meta(doctype).get_field(fieldname))
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

	def test_a_change_made_in_role_permission_manager_survives_migrate(self):
		setup_drea_finance()
		row = {"parent": "Company", "permlevel": 1, "role": "HR Manager"}
		frappe.db.set_value("Custom DocPerm", row, "write", 1)
		try:
			setup_drea_finance()  # what bench migrate runs
			self.assertEqual(frappe.db.get_value("Custom DocPerm", row, "write"), 1)
		finally:
			frappe.db.set_value("Custom DocPerm", row, "write", 0)


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


class FinanceStandIns:
	"""The few Finance tables the checks read, as throwaway stand-ins (Postgres only). Refuses to
	run where a real `finance` schema exists."""

	def make_finance_tables(self):
		if frappe.db.db_type != "postgres":
			self.skipTest("Finance's tables are only ever in the Postgres database")
		if frappe.db.sql("select to_regnamespace('finance')")[0][0]:
			self.skipTest("a real finance schema is here; not touching it")
		frappe.db.sql("create schema finance")
		frappe.db.sql("create table finance.users (id uuid primary key, frappe_user varchar(140))")
		frappe.db.sql("create table finance.wallet_entries (id uuid primary key, holder_id uuid, amount numeric(15,2))")
		frappe.db.sql(
			"create table finance.legal_entities (id uuid primary key, company varchar(140), entity_code varchar(40))"
		)
		frappe.db.sql(
			"create table finance.legal_entity_accounts (id uuid primary key, legal_entity_id uuid, is_active boolean)"
		)
		self.addCleanup(self.drop_finance_tables)

	def drop_finance_tables(self):
		frappe.db.sql("drop schema if exists finance cascade")
		# committed: the code under test may have committed the schema, and a rollback would bring it back
		frappe.db.commit()

	def finance_user(self, user: str) -> str:
		return frappe.db.sql(
			"insert into finance.users (id, frappe_user) values (gen_random_uuid(), %s) returning id", (user,)
		)[0][0]


ADMIN_TWO = "_test_finance_admin_two@example.com"


def make_user(email: str, **finance):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Finance Test", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
	if finance:
		frappe.db.set_value("User", email, finance)


class TestUserFinanceGuards(FinanceStandIns, IntegrationTestCase):
	"""Audit H2: the refusals Finance's user screen made, now in the desk."""

	def setUp(self):
		setup_drea_finance()
		make_user(TEST_USER, enabled=1, drea_finance_role="admin", drea_finance_active=1)
		make_user(ADMIN_TWO, enabled=1, drea_finance_role="staff", drea_finance_active=1)
		frappe.db.set_single_value("HR Settings", NO_PASSWORD_FIELD, "")
		# this site's other admins would hide the "last admin" case
		frappe.db.set_value(
			"User", {"drea_finance_role": "admin", "name": ["!=", TEST_USER]}, "drea_finance_role", "staff"
		)

	def save(self, user: str, **changes):
		doc = frappe.get_doc("User", user)
		doc.update(changes)
		doc.save(ignore_permissions=True)

	def test_the_last_active_admin_stays(self):
		for change in ({"drea_finance_role": "finance"}, {"drea_finance_active": 0}, {"enabled": 0}):
			with self.assertRaisesRegex(frappe.ValidationError, "last active Drea Finance admin"):
				self.save(TEST_USER, **change)
		# a service account that is admin does not count: it never signs in
		frappe.db.set_value("User", ADMIN_TWO, "drea_finance_role", "admin")
		frappe.db.set_single_value("HR Settings", NO_PASSWORD_FIELD, ADMIN_TWO)
		with self.assertRaisesRegex(frappe.ValidationError, "last active Drea Finance admin"):
			self.save(TEST_USER, drea_finance_role="finance")
		# a real second admin: now it may go
		frappe.db.set_single_value("HR Settings", NO_PASSWORD_FIELD, "")
		self.save(TEST_USER, drea_finance_role="finance")
		self.assertEqual(frappe.db.get_value("User", TEST_USER, "drea_finance_role"), "finance")

	def test_someone_holding_an_advance_is_not_switched_off(self):
		self.make_finance_tables()
		frappe.db.set_value("User", ADMIN_TWO, "drea_finance_role", "admin")  # not the last admin
		frappe.db.set_value("User", TEST_USER, "drea_finance_role", "staff")
		holder = self.finance_user(TEST_USER)
		frappe.db.sql(
			"insert into finance.wallet_entries values (gen_random_uuid(), %s, 150000)", (holder,)
		)
		for change in (
			{"drea_finance_active": 0},
			{"enabled": 0},
			{"drea_finance_role": ""},
			{"drea_finance_role": "finance"},
			{"drea_finance_role": "vendor"},
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Rp 150.000 of cash advance"):
				self.save(TEST_USER, **change)
		# a role that may hold an advance is fine
		self.save(TEST_USER, drea_finance_role="dept_head")
		# returned: the wallet is at zero, so they may go
		frappe.db.sql(
			"insert into finance.wallet_entries values (gen_random_uuid(), %s, -150000)", (holder,)
		)
		self.save(TEST_USER, drea_finance_active=0)
		self.assertEqual(frappe.db.get_value("User", TEST_USER, "drea_finance_active"), 0)

	def test_without_finance_tables_the_advance_check_is_skipped(self):
		frappe.db.set_value("User", ADMIN_TWO, "drea_finance_role", "admin")
		frappe.db.set_value("User", TEST_USER, "drea_finance_role", "staff")
		self.save(TEST_USER, drea_finance_active=0)
		self.assertEqual(frappe.db.get_value("User", TEST_USER, "drea_finance_active"), 0)


class TestCompanyFinanceGuards(FinanceStandIns, IntegrationTestCase):
	COMPANY = "_Test Company"

	def setUp(self):
		setup_drea_finance()
		frappe.db.set_value(
			"Company",
			self.COMPANY,
			{"withholding_tax_percent": 0, "withholding_kind": None, "drea_finance_active": 1},
		)

	def save(self, **changes):
		doc = frappe.get_doc("Company", self.COMPANY)
		doc.update(changes)
		doc.save(ignore_permissions=True)

	def test_withholding_rate_needs_a_kind_and_a_sane_percent(self):
		with self.assertRaisesRegex(frappe.ValidationError, "PPh 23 or PPh Final"):
			self.save(withholding_tax_percent=2)
		with self.assertRaisesRegex(frappe.ValidationError, "between 0 and 100"):
			self.save(withholding_tax_percent=120, withholding_kind="pph23")
		self.save(withholding_tax_percent=2, withholding_kind="pph23")
		self.assertEqual(frappe.db.get_value("Company", self.COMPANY, "withholding_kind"), "pph23")

	def test_a_company_with_bank_accounts_on_stays_on(self):
		self.make_finance_tables()
		entity = frappe.db.sql(
			"insert into finance.legal_entities values (gen_random_uuid(), %s) returning id", (self.COMPANY,)
		)[0][0]
		account = frappe.db.sql(
			"insert into finance.legal_entity_accounts values (gen_random_uuid(), %s, true) returning id",
			(entity,),
		)[0][0]
		with self.assertRaisesRegex(frappe.ValidationError, "1 bank account"):
			self.save(drea_finance_active=0)
		frappe.db.sql("update finance.legal_entity_accounts set is_active = false where id = %s", (account,))
		self.save(drea_finance_active=0)
		self.assertEqual(frappe.db.get_value("Company", self.COMPANY, "drea_finance_active"), 0)

	def test_the_finance_code_stays_once_finance_has_books_under_it(self):
		frappe.db.set_value("Company", self.COMPANY, "drea_finance_code", "LE-T1")
		self.save(drea_finance_code="LE-T2")  # no Finance tables here (before the cutover): free
		self.make_finance_tables()
		self.save(drea_finance_code="LE-T3")  # Finance has nothing under this company: free
		frappe.db.sql(
			"insert into finance.legal_entities values (gen_random_uuid(), %s, 'LE-T3')", (self.COMPANY,)
		)
		with self.assertRaisesRegex(frappe.ValidationError, "stays .*LE-T3"):
			self.save(drea_finance_code="LE-T4")
		with self.assertRaisesRegex(frappe.ValidationError, "stays .*LE-T3"):
			self.save(drea_finance_code="")
		self.save(drea_finance_code="LE-T3", withholding_tax_percent=0)  # other edits still save

	def test_a_code_finance_files_under_another_company_is_refused(self):
		frappe.db.set_value("Company", self.COMPANY, "drea_finance_code", "")
		self.make_finance_tables()
		frappe.db.sql("insert into finance.legal_entities values (gen_random_uuid(), 'Another Co', 'LE-T9')")
		with self.assertRaisesRegex(frappe.ValidationError, "already the Drea Finance code of"):
			self.save(drea_finance_code="LE-T9")
		self.save(drea_finance_code="LE-T8")


SERVICE = "_test_service_account@example.com"
STRONG = "Zx9!quartz-Lantern-2026"


class TestServiceAccountPasswords(IntegrationTestCase):
	"""Owner, 9 Nov 2026: the service accounts never get a password; everyone else keeps the reset."""

	def setUp(self):
		setup_drea_finance()
		make_user(SERVICE)
		make_user(TEST_USER)
		frappe.db.set_single_value("HR Settings", NO_PASSWORD_FIELD, f"{SERVICE.upper()}\nsomeone@else.invalid")

	def test_the_list_is_filled_once_and_then_belongs_to_the_system_manager(self):
		frappe.db.delete("Singles", {"doctype": "HR Settings", "field": NO_PASSWORD_FIELD})
		fill_no_password_users()
		self.assertEqual(no_password_users(), set(NO_PASSWORD_DEFAULT))
		frappe.db.set_single_value("HR Settings", NO_PASSWORD_FIELD, "")
		fill_no_password_users()
		self.assertEqual(no_password_users(), set())
		meta = frappe.get_meta("HR Settings")
		self.assertEqual(meta.get_field(NO_PASSWORD_FIELD).permlevel, 1)
		writers = {p.role for p in meta.permissions if p.permlevel == 1 and p.write}
		self.assertEqual(writers, {"System Manager"})

	def test_they_never_sign_in_and_everyone_else_does(self):
		self.assertIn("hrms.finance.refuse_service_account_login", frappe.get_hooks("on_login"))
		with self.assertRaisesRegex(frappe.AuthenticationError, "does not sign in"):
			refuse_service_account_login(SimpleNamespace(user=SERVICE))
		refuse_service_account_login(SimpleNamespace(user=TEST_USER))

	def test_the_finance_address_and_key_are_the_system_managers(self):
		meta = frappe.get_meta("HR Settings")
		for field in ("drea_finance_url", "drea_finance_api_key", "drea_finance_paused"):
			self.assertEqual(meta.get_field(field).permlevel, 1, field)

	def test_setting_a_password_is_refused_for_them_only(self):
		user = frappe.get_doc("User", SERVICE)
		user.new_password = STRONG
		with self.assertRaisesRegex(frappe.ValidationError, "never gets a password"):
			user.save(ignore_permissions=True)
		other = frappe.get_doc("User", TEST_USER)
		other.new_password = STRONG
		other.save(ignore_permissions=True)

	def test_no_reset_link_is_made_for_them(self):
		from frappe.core.doctype.user.user import reset_password

		frappe.db.set_value("User", SERVICE, "reset_password_key", "")
		reset_password(SERVICE)  # the same answer as for anyone: nothing to tell an attacker
		self.assertFalse(frappe.db.get_value("User", SERVICE, "reset_password_key"))
		with self.assertRaisesRegex(frappe.ValidationError, "never gets a password"):
			frappe.get_doc("User", SERVICE).validate_reset_password()
		frappe.get_doc("User", TEST_USER).validate_reset_password()  # everyone else: allowed

	def test_a_link_sent_earlier_cannot_set_their_password(self):
		from frappe.utils import now_datetime
		from frappe.utils.data import sha256_hash

		from hrms.finance import update_password

		frappe.db.set_value(
			"User",
			SERVICE,
			{"reset_password_key": sha256_hash("old-link"), "last_reset_password_key_generated_on": now_datetime()},
		)
		with self.assertRaisesRegex(frappe.ValidationError, "never gets a password"):
			update_password(new_password=STRONG, key="old-link")
		self.assertEqual(
			frappe.get_hooks("override_whitelisted_methods")["frappe.core.doctype.user.user.update_password"][-1],
			"hrms.finance.update_password",
		)

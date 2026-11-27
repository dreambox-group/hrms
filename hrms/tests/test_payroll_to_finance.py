# Copyright (c) 2026, Dreambox and contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

import frappe
from frappe.tests import IntegrationTestCase

from hrms.payroll import drea_finance as df

COMPANY = {"CV Denalo": "LE-00002", "CV Kotak": "LE-00004"}
DIVISION = {
	"Finance - Db": "DV-00001",
	"HR - Db": "DV-00001",
	"Digital - Db": "DV-00002",
	"Unmapped - Db": None,
}
COMPONENTS = {
	"Basic": "SALARY",
	"Arrear": "SALARY",
	"Incentive": "INCENTIVE",
	"Late Penalty": "SALARY",
	"Prive": "PRIVE",
	"PPh21": "PPH21_WITHHELD",
	"BPJS JHT": "BPJS_TK_COMPANY",
	"BPJS JKM": None,
	"Leave Encashment": None,
	"Mystery": "NOT_IN_THE_TABLE",
}
CODES = {
	"SALARY": {"name": "Gaji", "kind": "earning", "account": "510201", "owed_account": None},
	"INCENTIVE": {"name": "Insentif", "kind": "earning", "account": "510202", "owed_account": None},
	"PRIVE": {"name": "Prive", "kind": "earning", "account": "310200", "owed_account": None},
	"PPH21_WITHHELD": {"name": "PPh 21", "kind": "deduction", "account": None, "owed_account": "210421"},
	"BPJS_TK_COMPANY": {"name": "BPJS TK", "kind": "employer", "account": "510402", "owed_account": "210302"},
}


def slip(
	name,
	company="CV Denalo",
	department="Finance - Db",
	net_pay=0,
	rounded_total=None,
	account="0231256511",
	**extra,
):
	return {
		"name": name,
		"employee": f"E-{name[3:]}",
		"employee_name": f"Person {name[3:]}",
		"company": company,
		"department": department,
		"net_pay": net_pay,
		"rounded_total": net_pay if rounded_total is None else rounded_total,
		"bank_name": "BCA - Kelapa Gading" if account else None,
		"bank_account_no": account,
		"account_name": f"PERSON {name[3:]}" if account else None,
		**extra,
	}


def line(parentfield, component, amount, **flags):
	return {"parentfield": parentfield, "salary_component": component, "amount": amount, **flags}


def summarise(slips, lines, use_net_pay=0):
	return df.summarise(slips, lines, COMPANY, DIVISION, COMPONENTS, CODES, use_net_pay)


class TestSummarise(IntegrationTestCase):
	def test_people_add_up_to_the_rows(self):
		slips = [
			slip("SS-1", department="Finance - Db", net_pay=9_000_000),
			slip("SS-2", department="HR - Db", net_pay=7_950_000),
			slip("SS-3", department="Digital - Db", net_pay=5_000_000),
		]
		lines = {
			"SS-1": [line("earnings", "Basic", 9_500_000), line("deductions", "PPh21", 500_000)],
			"SS-2": [
				line("earnings", "Basic", 8_000_000),
				line("deductions", "Late Penalty", 50_000),  # a cut the company keeps -> reduces SALARY
				line("employer_contributions", "BPJS JHT", 296_000),
				line("employer_contributions", "BPJS JKM", 24_000),  # unmapped employer share: left out
			],
			"SS-3": [line("earnings", "Basic", 4_000_000), line("earnings", "Incentive", 1_000_000)],
		}
		sent = summarise(slips, lines)
		self.assertEqual(
			sent["rows"],
			[
				{
					"company_code": "LE-00002",
					"division_code": "DV-00001",
					"headcount": 2,
					"amounts": {"BPJS_TK_COMPANY": 296_000, "PPH21_WITHHELD": 500_000, "SALARY": 17_450_000},
					"take_home": 16_950_000,
				},
				{
					"company_code": "LE-00002",
					"division_code": "DV-00002",
					"headcount": 1,
					"amounts": {"INCENTIVE": 1_000_000, "SALARY": 4_000_000},
					"take_home": 5_000_000,
				},
			],
		)
		self.assertEqual(
			sent["people"][1],
			{
				"employee_id": "E-2",
				"name": "Person 2",
				"company_code": "LE-00002",
				"division_code": "DV-00001",
				"account_number": "0231256511",  # text: the leading zero stays
				"bank": "BCA - Kelapa Gading",
				"account_name": "PERSON 2",
				"amounts": {"BPJS_TK_COMPANY": 296_000, "SALARY": 7_950_000},
				"take_home": 7_950_000,
			},
		)
		self.assertEqual([p["employee_id"] for p in sent["people"]], ["E-1", "E-2", "E-3"])
		# only the codes used, each with the accounts its kind books to
		self.assertEqual(
			sent["components"],
			[
				{
					"code": "BPJS_TK_COMPANY",
					"name": "BPJS TK",
					"kind": "employer",
					"account": "510402",
					"owed_account": "210302",
				},
				{"code": "INCENTIVE", "name": "Insentif", "kind": "earning", "account": "510202"},
				{"code": "PPH21_WITHHELD", "name": "PPh 21", "kind": "deduction", "owed_account": "210421"},
				{"code": "SALARY", "name": "Gaji", "kind": "earning", "account": "510201"},
			],
		)
		# a person goes by employee number and name; no slip, department or company name leaves
		text = frappe.as_json(sent)
		for internal in ("SS-1", "SS-2", "SS-3", "Finance - Db", "CV Denalo"):
			self.assertNotIn(internal, text)

	def test_prive_and_someone_without_a_bank_account(self):
		sent = summarise(
			[slip("SS-7", net_pay=10_000_000), slip("SS-8", net_pay=3_000_000, account="  ")],
			{
				"SS-7": [line("earnings", "Prive", 10_000_000)],
				"SS-8": [line("earnings", "Basic", 3_000_000)],
			},
		)
		partner, staff = sent["people"]
		self.assertEqual(partner["amounts"], {"PRIVE": 10_000_000})
		self.assertEqual(partner["take_home"], 10_000_000)
		# no account: the bank fields are left out, and Drea Finance lists the person to pay by hand
		self.assertNotIn("account_number", staff)
		self.assertNotIn("bank", staff)
		self.assertNotIn("account_name", staff)
		self.assertIn(
			{"code": "PRIVE", "name": "Prive", "kind": "earning", "account": "310200"}, sent["components"]
		)
		self.assertEqual(sent["rows"][0]["amounts"], {"PRIVE": 10_000_000, "SALARY": 3_000_000})
		self.assertEqual(sent["rows"][0]["take_home"], 13_000_000)

	def test_statistical_and_do_not_include_lines_are_skipped(self):
		sent = summarise(
			[slip("SS-1", net_pay=1_000_000)],
			{
				"SS-1": [
					line("earnings", "Basic", 1_000_000),
					line("earnings", "Arrear", 999, statistical_component=1),
					line("earnings", "Incentive", 777, do_not_include_in_total=1),
				]
			},
		)
		self.assertEqual(sent["rows"][0]["amounts"], {"SALARY": 1_000_000})
		self.assertEqual([c["code"] for c in sent["components"]], ["SALARY"])

	def test_take_home_uses_rounded_total_unless_rounding_is_off(self):
		slips = [slip("SS-1", net_pay=1_000_000.4, rounded_total=1_000_000)]
		lines = {"SS-1": [line("earnings", "Basic", 1_000_000.4)]}
		self.assertEqual(summarise(slips, lines)["people"][0]["take_home"], 1_000_000)
		self.assertEqual(summarise(slips, lines, use_net_pay=1)["people"][0]["take_home"], 1_000_000)

	def test_stops_and_lists_every_problem(self):
		slips = [
			slip("SS-1", company="CV Unknown", net_pay=1),
			slip("SS-2", department=None, net_pay=1),
			slip("SS-3", department="Unmapped - Db", net_pay=1),
			slip("SS-4", net_pay=1_000_000),
			slip("SS-5", company="CV Kotak", net_pay=900_000),
			slip("SS-6", net_pay=5),
		]
		lines = {
			"SS-4": [line("earnings", "Leave Encashment", 1_000_000)],  # unmapped earning
			"SS-5": [line("earnings", "Basic", 1_000_000)],  # take-home 900k doesn't add up
			"SS-6": [line("earnings", "Mystery", 5)],  # a code with no accounts
		}
		with self.assertRaises(df.PayrollSendError) as caught:
			summarise(slips, lines)
		message = str(caught.exception)
		for expected in (
			"Company CV Unknown has no legal entity code in Drea Finance Settings",
			"Salary Slip SS-2 has no department",
			"Department Unmapped - Db has no division in Drea Finance Settings",
			"Salary Component Leave Encashment has no pay code in Drea Finance Settings",
			"Salary Slip SS-5 (E-5): take-home is 900000 but the earnings less the deductions come to 1000000",
			"Pay code NOT_IN_THE_TABLE (Salary Component Mystery) has no accounts in Drea Finance Settings",
		):
			self.assertIn(expected, message)

	def test_a_code_in_the_wrong_table_stops(self):
		with self.assertRaises(df.PayrollSendError):
			summarise(
				[slip("SS-1", net_pay=1_000_000)],
				{"SS-1": [line("earnings", "Basic", 1_000_000), line("earnings", "PPh21", 5)]},
			)


class TestVersions(IntegrationTestCase):
	def test_next_version(self):
		self.assertEqual(df.next_version(0, None, "a"), 1)
		self.assertEqual(df.next_version(1, "a", "a"), 1)  # same figures: Finance answers unchanged
		self.assertEqual(df.next_version(1, "a", "b"), 2)

	def test_hash_ignores_nothing_that_matters(self):
		base = {
			"month": "2026-11",
			"kind": "salary",
			"pay_date": "2026-11-25",
			"components": [{"code": "SALARY", "account": "510201"}],
			"rows": [{"take_home": 1}],
			"people": [{"employee_id": "E-1", "account_number": "01", "take_home": 1}],
		}
		self.assertEqual(df.figures_hash(base), df.figures_hash(dict(base)))
		for changed in (
			{"pay_date": "2026-11-26"},
			{"kind": "thr"},
			{"components": [{"code": "SALARY", "account": "510299"}]},  # an account changed
			{"people": [{"employee_id": "E-1", "account_number": "02", "take_home": 1}]},  # a bank account
		):
			self.assertNotEqual(df.figures_hash(base), df.figures_hash({**base, **changed}), changed)


def set_mappings(companies=None, departments=None, pay_codes=None, codes=None, **connection):
	"""Write Drea Finance Settings directly (tests only): the rows given replace what is there."""
	settings = frappe.get_single("Drea Finance Settings")
	settings.update(connection)
	if codes is not None:
		settings.set(
			"codes",
			[
				{
					"pay_code": c,
					"code_name": v["name"],
					"kind": v["kind"],
					"account": v["account"],
					"owed_account": v["owed_account"],
				}
				for c, v in codes.items()
			],
		)
	if companies is not None:
		settings.set("companies", [{"company": c, "entity_code": e} for c, e in companies.items()])
	if departments is not None:
		settings.set("departments", [{"department": d, "division": v} for d, v in departments.items()])
	if pay_codes is not None:
		settings.set("pay_codes", [{"salary_component": c, "pay_code": p} for c, p in pay_codes.items()])
	settings.flags.ignore_mandatory = True
	settings.save()
	return settings


class TestPayCodeMapping(IntegrationTestCase):
	def component(self, name, type_):
		if not frappe.db.exists("Salary Component", name):
			frappe.get_doc({"doctype": "Salary Component", "salary_component": name, "type": type_}).insert()
		return name

	def test_codes_must_fit_the_component_type(self):
		earning = self.component("_Test DF Earning", "Earning")
		deduction = self.component("_Test DF Deduction", "Deduction")
		employer = self.component("_Test DF Employer", "Employer Contribution")
		set_mappings(
			codes=CODES, pay_codes={earning: "SALARY", deduction: "SALARY", employer: "BPJS_TK_COMPANY"}
		)
		set_mappings(pay_codes={deduction: "PPH21_WITHHELD"})
		for name, code in (
			(earning, "PPH21_WITHHELD"),
			(deduction, "BPJS_KES_COMPANY"),
			(employer, "SALARY"),
		):
			with self.assertRaises(frappe.ValidationError):
				set_mappings(pay_codes={name: code})
		# a code that is not in Pay Codes -> Drea Finance Accounts
		with self.assertRaises(frappe.ValidationError):
			set_mappings(pay_codes={earning: "BONUS"})

	def test_each_kind_books_to_its_accounts(self):
		set_mappings(
			pay_codes={},
			codes={
				"bonus": {"name": " Bonus ", "kind": "earning", "account": " 510202 ", "owed_account": None}
			},
		)
		row = frappe.get_single("Drea Finance Settings").codes[0]
		self.assertEqual((row.pay_code, row.code_name, row.account), ("BONUS", "Bonus", "510202"))
		for bad in (
			{"kind": "earning", "account": "510202", "owed_account": "210201"},  # pay is owed on nothing
			{"kind": "earning", "account": None, "owed_account": None},
			{"kind": "deduction", "account": "510202", "owed_account": "210421"},  # a deduction is no cost
			{"kind": "deduction", "account": None, "owed_account": None},
			{"kind": "employer", "account": "510401", "owed_account": None},
			{"kind": "employer", "account": "51040", "owed_account": "210301"},  # six digits
			{"kind": "", "account": "510401", "owed_account": "210301"},
		):
			with self.assertRaises(frappe.ValidationError, msg=bad):
				set_mappings(codes={"BONUS": {"name": "Bonus", **bad}})
		with self.assertRaises(frappe.ValidationError):
			set_mappings(codes={"SALARY-1": CODES["SALARY"]})  # not a code Drea Finance takes
		settings = frappe.get_single("Drea Finance Settings")
		settings.set(
			"codes", [{"pay_code": "SALARY", "code_name": "Gaji", "kind": "earning", "account": "510201"}] * 2
		)
		self.assertRaises(frappe.ValidationError, settings.save)

	def test_entity_codes_are_checked_and_unique(self):
		companies = frappe.get_all("Company", pluck="name", limit=2)
		with self.assertRaises(frappe.ValidationError):
			set_mappings(companies={companies[0]: "LE-1"})
		if len(companies) == 2:
			settings = frappe.get_single("Drea Finance Settings")
			settings.set("companies", [{"company": c, "entity_code": "LE-00009"} for c in companies])
			self.assertRaises(frappe.ValidationError, settings.save)
		set_mappings(companies={companies[0]: "le-00009"})
		self.assertEqual(frappe.get_single("Drea Finance Settings").companies[0].entity_code, "LE-00009")


class TestSeparation(IntegrationTestCase):
	def test_payroll_entry_keeps_its_send_status(self):
		for field in (
			"drea_finance_kind",
			"drea_finance_run_id",
			"drea_finance_version",
			"drea_finance_hash",
			"drea_finance_status",
		):
			self.assertTrue(frappe.get_meta("Payroll Entry").has_field(field), field)
			if field != "drea_finance_kind":
				self.assertTrue(frappe.get_meta("Payroll Entry").get_field(field).no_copy, field)
		section = frappe.get_meta("Payroll Entry").get_field("drea_finance_section")
		self.assertEqual(section.depends_on, "eval:frappe.boot.drea_finance_enabled")

	def test_hr_forms_carry_no_drea_finance_fields(self):
		for doctype in ("Company", "Department", "Salary Component", "User", "HR Settings"):
			finance = [
				f.fieldname for f in frappe.get_meta(doctype).fields if "drea_finance" in (f.fieldname or "")
			]
			self.assertEqual(finance, [], doctype)
		self.assertFalse(frappe.db.exists("DocType", "User Division"))

	def test_drea_hr_runs_without_drea_finance(self):
		set_mappings(enabled=0, send_payroll=1)
		self.assertFalse(df.settings()["enabled"])
		with patch.object(df.frappe, "enqueue") as enqueue:
			df.queue_after_submission("HR-PRUN-NOT-SENT")
		enqueue.assert_not_called()
		set_mappings(enabled=1, url="https://f.invalid", send_payroll=1)
		self.assertTrue(df.settings()["enabled"])
		set_mappings(enabled=0)

	def test_each_settings_area_has_its_own_module(self):
		# A sidebar claims every workspace of its module, and the desk opens a workspace in the first
		# sidebar that claims it: filed under HR Setup, Drea Settings took over /desk/hr-setup. Filed
		# under HR it vanished from the dock, because hooks.py makes HR a code-only module.
		from frappe.desk.doctype.sidebar.sidebar import get_navigable_modules

		for sidebar in ("Drea Settings", "Drea Finance"):
			module = frappe.db.get_value("Sidebar", sidebar, "module")
			self.assertEqual(module, sidebar)
			self.assertEqual(frappe.db.get_value("Module Def", module, "app_name"), "hrms")
			self.assertFalse(frappe.get_all("Workspace", filters={"module": module}, limit=1))
			self.assertIn(module, get_navigable_modules())
		# Division is Drea Finance's, not in HR's settings menu
		items = frappe.get_all("Sidebar Item", filters={"parent": "Drea Settings"}, pluck="link_to")
		self.assertNotIn("Division", items)


def response(status, body):
	r = MagicMock()
	r.ok = 200 <= status < 300
	r.status_code = status
	r.json.return_value = body
	r.text = frappe.as_json(body)
	return r


class FakeEntry(SimpleNamespace):
	def db_set(self, values, value=None, update_modified=True):
		if isinstance(values, str):
			values = {values: value}
		self.written.update(values)
		for k, v in values.items():
			setattr(self, k, v)


PAYLOAD = {
	"month": "2026-11",
	"kind": "salary",
	"pay_date": "2026-11-25",
	"components": [{"code": "SALARY", "name": "Gaji", "kind": "earning", "account": "510201"}],
	"rows": [{"take_home": 1}],
	"people": [{"employee_id": "E-1", "take_home": 1}],
}


class TestSend(IntegrationTestCase):
	def setUp(self):
		self.real_get_doc = frappe.get_doc
		self.entry = FakeEntry(name="HR-PRUN-TEST-1", amended_from=None, written={})
		patches = [
			patch.object(df.frappe, "get_doc", side_effect=self.get_doc),
			patch.object(df, "build_payload", return_value=dict(PAYLOAD)),
			patch.object(df, "run_history", return_value=("HR-PRUN-TEST-1", 0, None)),
			patch.object(
				df,
				"settings",
				return_value={"url": "https://f.invalid", "key": "k", "enabled": 1, "test_only": 0},
			),
			patch.object(df.time, "sleep"),
		]
		for p in patches:
			p.start()
			self.addCleanup(p.stop)

	def get_doc(self, *args, **kwargs):
		if args and args[0] == "Payroll Entry":
			return self.entry
		return self.real_get_doc(*args, **kwargs)

	def test_real_send_stores_the_version_and_the_answer(self):
		with patch.object(
			df.requests,
			"post",
			return_value=response(
				201,
				{
					"ok": True,
					"status": "received",
					"message": "Received.",
					"summary": {"totals": {"people": 1, "gross": 0, "prive": 1, "take_home": 1}},
				},
			),
		) as post:
			result = df.send(self.entry.name)
		sent = post.call_args.kwargs["json"]
		self.assertEqual(sent["hr_run_id"], "HR-PRUN-TEST-1")
		self.assertEqual(sent["version"], 1)
		self.assertFalse(sent["dry_run"])
		self.assertEqual(
			set(sent),
			{"hr_run_id", "version", "dry_run", "month", "kind", "pay_date", "components", "rows", "people"},
		)
		self.assertEqual(post.call_args.kwargs["headers"]["X-API-Key"], "k")
		self.assertTrue(result["ok"])
		self.assertEqual(self.entry.written["drea_finance_version"], 1)
		self.assertEqual(self.entry.written["drea_finance_hash"], df.figures_hash(PAYLOAD))
		self.assertIn("received", self.entry.written["drea_finance_status"])
		self.assertIn("1 people, take-home 1, of which prive 1", self.entry.written["drea_finance_status"])

	def test_a_test_send_stores_no_version(self):
		with patch.object(
			df.requests,
			"post",
			return_value=response(200, {"ok": True, "status": "dry_run", "message": "ok"}),
		) as post:
			df.send(self.entry.name, test=True)
		self.assertTrue(post.call_args.kwargs["json"]["dry_run"])
		self.assertNotIn("drea_finance_version", self.entry.written)
		self.assertIn("Test", self.entry.written["drea_finance_status"])

	def test_a_refusal_is_written_for_hr_and_not_retried(self):
		body = {
			"error": "The payroll was not accepted.",
			"problems": ["Row 1: DV-00099 is not a division code."],
		}
		with patch.object(df.requests, "post", return_value=response(422, body)) as post:
			result = df.send(self.entry.name)
		self.assertEqual(post.call_count, 1)
		self.assertFalse(result["ok"])
		self.assertNotIn("drea_finance_version", self.entry.written)
		self.assertIn("DV-00099", self.entry.written["drea_finance_status"])

	def test_a_version_clash_is_sent_once_more_as_the_next_version(self):
		clash = response(409, {"error": "Version 1 was already received with different figures."})
		ok = response(201, {"ok": True, "status": "received", "message": "Received."})
		with patch.object(df.requests, "post", side_effect=[clash, ok]) as post:
			result = df.send(self.entry.name)
		self.assertEqual([c.kwargs["json"]["version"] for c in post.call_args_list], [1, 2])
		self.assertTrue(result["ok"])
		self.assertEqual(self.entry.written["drea_finance_version"], 2)
		# a second clash is left to a person
		with patch.object(df.requests, "post", side_effect=[clash, clash]) as post:
			result = df.send(self.entry.name)
		self.assertEqual(post.call_count, 2)
		self.assertFalse(result["ok"])
		self.assertIn("refused (409)", self.entry.written["drea_finance_status"])

	def test_server_errors_and_network_errors_are_retried_three_times(self):
		with patch.object(df.requests, "post", return_value=response(503, {"error": "down"})) as post:
			df.send(self.entry.name)
		self.assertEqual(post.call_count, 3)
		with patch.object(df.requests, "post", side_effect=requests.ConnectionError()) as post:
			with self.assertRaises(df.PayrollSendError):
				df.send(self.entry.name)
		self.assertEqual(post.call_count, 3)
		self.assertIn("could not be reached", self.entry.written["drea_finance_status"])

	def test_automatic_send_does_nothing_while_switched_off(self):
		with (
			patch.object(df, "settings", return_value={"url": "u", "key": "k", "enabled": 0, "test_only": 0}),
			patch.object(df.requests, "post") as post,
		):
			self.assertEqual(df.send(self.entry.name, automatic=True), {"status": "off"})
		post.assert_not_called()

	def test_a_build_problem_is_written_and_nothing_is_sent(self):
		with (
			patch.object(
				df,
				"build_payload",
				side_effect=df.PayrollSendError("Salary Component X has no Drea Finance code."),
			),
			patch.object(df.requests, "post") as post,
		):
			with self.assertRaises(df.PayrollSendError):
				df.send(self.entry.name)
		post.assert_not_called()
		self.assertIn("Not sent", self.entry.written["drea_finance_status"])


class TestRealPayrollEntry(IntegrationTestCase):
	"""A real Payroll Entry on _Test Company, end to end up to the HTTP call."""

	def setUp(self):
		from hrms.payroll.doctype.payroll_entry.test_payroll_entry import TestPayrollEntry

		TestPayrollEntry.setUp(self)
		frappe.db.set_single_value("Payroll Settings", "email_salary_slip_to_employee", 0)
		if not frappe.db.exists("Division", "DV-TEST1"):
			frappe.get_doc(
				{
					"doctype": "Division",
					"division_code": "DV-TEST1",
					"division_name": "Payroll Test Division",
					"is_active": 1,
				}
			).insert()

	def test_totals_match_the_slips_and_amendments_continue_the_run(self):
		from erpnext.setup.doctype.employee.test_employee import make_employee

		from hrms.payroll.doctype.payroll_entry.payroll_entry import get_start_end_dates
		from hrms.payroll.doctype.payroll_entry.test_payroll_entry import (
			make_payroll_entry,
			setup_salary_structure,
		)
		from hrms.tests.test_utils import create_department

		department = create_department("Drea Payroll Test")
		set_mappings(
			companies={"_Test Company": "LE-00091"},
			departments={department: "DV-TEST1"},
			pay_codes={},
			codes=CODES,
			enabled=1,
			url="https://f.invalid",
			send_payroll=1,
		)
		company = frappe.get_doc("Company", "_Test Company")
		employees = [
			make_employee(f"drea.payroll{i}@example.com", company=company.name, department=department)
			for i in (1, 2)
		]
		for employee in employees:
			frappe.db.set_value("Employee", employee, "department", department)
			setup_salary_structure(employee, company)

		dates = get_start_end_dates("Monthly", frappe.utils.nowdate())
		with patch("hrms.payroll.drea_finance.queue_after_submission") as queued:
			entry = make_payroll_entry(
				start_date=dates.start_date,
				end_date=dates.end_date,
				payable_account=company.default_payroll_payable_account,
				currency=company.default_currency,
				company=company.name,
				cost_center="Main - _TC",
				department=department,
			)
		queued.assert_called_once_with(entry.name)

		# an unmapped component stops the send with a plain message ...
		with self.assertRaises(df.PayrollSendError):
			df.build_payload(frappe.get_doc("Payroll Entry", entry.name))
		# ... and once every component has a code, the totals go
		set_mappings(
			pay_codes={
				component: {"Earning": "SALARY", "Deduction": "PPH21_WITHHELD"}[type_]
				for component, type_ in frappe.get_all(
					"Salary Component", fields=["name", "type"], as_list=True
				)
				if type_ in ("Earning", "Deduction")
			}
		)
		payload = df.build_payload(frappe.get_doc("Payroll Entry", entry.name))
		slips = frappe.get_all(
			"Salary Slip", filters={"payroll_entry": entry.name, "docstatus": 1}, fields=["rounded_total"]
		)
		self.assertEqual(len(payload["rows"]), 1)
		row = payload["rows"][0]
		self.assertEqual((row["company_code"], row["division_code"]), ("LE-00091", "DV-TEST1"))
		self.assertEqual(row["headcount"], len(slips))
		self.assertEqual(row["take_home"], sum(round(s.rounded_total) for s in slips))
		self.assertEqual(payload["month"], str(dates.end_date)[:7])
		# one line per person, adding up to the row; no bank account on file: no bank fields
		self.assertEqual(sorted(p["employee_id"] for p in payload["people"]), sorted(employees))
		self.assertEqual(sum(p["take_home"] for p in payload["people"]), row["take_home"])
		self.assertTrue(all("account_number" not in p for p in payload["people"]))
		self.assertEqual({c["code"] for c in payload["components"]}, set(row["amounts"]))

		ok = response(201, {"ok": True, "status": "received", "message": "Received."})
		with (
			patch.object(
				df,
				"settings",
				return_value={"url": "https://f.invalid", "key": "k", "enabled": 1, "test_only": 0},
			),
			patch.object(df.requests, "post", return_value=ok) as post,
		):
			df.send(entry.name)
			self.assertEqual(post.call_args.kwargs["json"]["version"], 1)
			self.assertEqual(frappe.db.get_value("Payroll Entry", entry.name, "drea_finance_version"), 1)
			self.assertEqual(df.run_history(frappe.get_doc("Payroll Entry", entry.name))[:2], (entry.name, 1))
			# the same figures again keep version 1
			df.send(entry.name)
			self.assertEqual(post.call_args.kwargs["json"]["version"], 1)

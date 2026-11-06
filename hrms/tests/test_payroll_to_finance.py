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
	"PPh21": "PPH21_WITHHELD",
	"BPJS Kesehatan Employee": "BPJS_KES_EMPLOYEE",
	"BPJS JHT": "BPJS_TK_COMPANY",
	"BPJS JKM": None,
	"Leave Encashment": None,
}


def slip(name, company="CV Denalo", department="Finance - Db", net_pay=0, rounded_total=None):
	return {
		"name": name,
		"company": company,
		"department": department,
		"net_pay": net_pay,
		"rounded_total": net_pay if rounded_total is None else rounded_total,
	}


def line(parentfield, component, amount, **flags):
	return {"parentfield": parentfield, "salary_component": component, "amount": amount, **flags}


def summarise(slips, lines, use_net_pay=0):
	return df.summarise(slips, lines, COMPANY, DIVISION, COMPONENTS, use_net_pay)


class TestSummarise(IntegrationTestCase):
	def test_groups_by_company_and_division_and_never_names_anyone(self):
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
		rows = summarise(slips, lines)
		self.assertEqual(
			rows,
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
		text = frappe.as_json(rows)
		for personal in ("SS-1", "SS-2", "SS-3", "Finance - Db", "CV Denalo"):
			self.assertNotIn(personal, text)

	def test_statistical_and_do_not_include_lines_are_skipped(self):
		rows = summarise(
			[slip("SS-1", net_pay=1_000_000)],
			{
				"SS-1": [
					line("earnings", "Basic", 1_000_000),
					line("earnings", "Arrear", 999, statistical_component=1),
					line("earnings", "Incentive", 777, do_not_include_in_total=1),
				]
			},
		)
		self.assertEqual(rows[0]["amounts"], {"SALARY": 1_000_000})

	def test_take_home_uses_rounded_total_unless_rounding_is_off(self):
		slips = [slip("SS-1", net_pay=1_000_000.4, rounded_total=1_000_000)]
		lines = {"SS-1": [line("earnings", "Basic", 1_000_000.4)]}
		self.assertEqual(summarise(slips, lines)[0]["take_home"], 1_000_000)
		self.assertEqual(summarise(slips, lines, use_net_pay=1)[0]["take_home"], 1_000_000)

	def test_stops_and_lists_every_problem(self):
		slips = [
			slip("SS-1", company="CV Unknown", net_pay=1),
			slip("SS-2", department=None, net_pay=1),
			slip("SS-3", department="Unmapped - Db", net_pay=1),
			slip("SS-4", net_pay=1_000_000),
			slip("SS-5", company="CV Kotak", net_pay=900_000),
		]
		lines = {
			"SS-4": [line("earnings", "Leave Encashment", 1_000_000)],  # unmapped earning
			"SS-5": [line("earnings", "Basic", 1_000_000)],  # take-home 900k doesn't add up
		}
		with self.assertRaises(df.PayrollSendError) as caught:
			summarise(slips, lines)
		message = str(caught.exception)
		for expected in (
			"Company CV Unknown has no Drea Finance code",
			"Salary Slip SS-2 has no department",
			"Department Unmapped - Db has no Drea Finance division",
			"Salary Component Leave Encashment has no Drea Finance code",
			"LE-00004 / DV-00001: take-home is 900000 but the earnings less the deductions come to 1000000",
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
		base = {"month": "2026-11", "kind": "salary", "pay_date": "2026-11-25", "rows": [{"take_home": 1}]}
		self.assertEqual(df.figures_hash(base), df.figures_hash(dict(base)))
		self.assertNotEqual(df.figures_hash(base), df.figures_hash({**base, "pay_date": "2026-11-26"}))
		self.assertNotEqual(df.figures_hash(base), df.figures_hash({**base, "kind": "thr"}))


class TestComponentCode(IntegrationTestCase):
	def check(self, type_, code):
		df.validate_component(frappe._dict(type=type_, drea_finance_component=code))

	def test_codes_fit_the_component_type(self):
		self.check("Earning", "SALARY")
		self.check("Deduction", "SALARY")  # a cut the company keeps
		self.check("Deduction", "PPH21_WITHHELD")
		self.check("Employer Contribution", "BPJS_TK_COMPANY")
		self.check("Earning", None)
		for type_, code in (
			("Earning", "PPH21_WITHHELD"),
			("Deduction", "BPJS_KES_COMPANY"),
			("Employer Contribution", "SALARY"),
		):
			with self.assertRaises(frappe.ValidationError):
				self.check(type_, code)


class TestFields(IntegrationTestCase):
	def test_migrate_made_the_fields(self):
		self.assertTrue(frappe.get_meta("Salary Component").has_field("drea_finance_component"))
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
		for field in ("drea_finance_send_payroll", "drea_finance_payroll_test_only"):
			self.assertTrue(frappe.get_meta("HR Settings").has_field(field), field)

	def test_drea_settings_does_not_claim_a_workspace(self):
		# A sidebar claims every workspace of its module, and the desk opens a workspace in the first
		# sidebar that claims it. Filed under HR Setup, Drea Settings took over /desk/hr-setup.
		module = frappe.db.get_value("Sidebar", "Drea Settings", "module")
		self.assertEqual(module, "HR")
		self.assertFalse(frappe.get_all("Workspace", filters={"module": module}, limit=1))


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


PAYLOAD = {"month": "2026-11", "kind": "salary", "pay_date": "2026-11-25", "rows": [{"take_home": 1}]}


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
					"summary": {"totals": {"people": 1, "take_home": 1}},
				},
			),
		) as post:
			result = df.send(self.entry.name)
		sent = post.call_args.kwargs["json"]
		self.assertEqual(sent["hr_run_id"], "HR-PRUN-TEST-1")
		self.assertEqual(sent["version"], 1)
		self.assertFalse(sent["dry_run"])
		self.assertEqual(set(sent), {"hr_run_id", "version", "dry_run", "month", "kind", "pay_date", "rows"})
		self.assertEqual(post.call_args.kwargs["headers"]["X-API-Key"], "k")
		self.assertTrue(result["ok"])
		self.assertEqual(self.entry.written["drea_finance_version"], 1)
		self.assertEqual(self.entry.written["drea_finance_hash"], df.figures_hash(PAYLOAD))
		self.assertIn("received", self.entry.written["drea_finance_status"])

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
		frappe.db.set_value("Company", "_Test Company", "drea_finance_code", "LE-TEST1")
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
		frappe.db.set_value("Department", department, "drea_finance_division", "DV-TEST1")
		company = frappe.get_doc("Company", "_Test Company")
		employees = [
			make_employee(f"drea.payroll{i}@example.com", company=company.name, department=department)
			for i in (1, 2)
		]
		for employee in employees:
			frappe.db.set_value("Employee", employee, "department", department)
			setup_salary_structure(employee, company)

		frappe.db.set_single_value("HR Settings", "drea_finance_send_payroll", 1)
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
		for component, type_ in frappe.get_all("Salary Component", fields=["name", "type"], as_list=True):
			code = {"Earning": "SALARY", "Deduction": "PPH21_WITHHELD"}.get(type_)
			frappe.db.set_value("Salary Component", component, "drea_finance_component", code)
		payload = df.build_payload(frappe.get_doc("Payroll Entry", entry.name))
		slips = frappe.get_all(
			"Salary Slip", filters={"payroll_entry": entry.name, "docstatus": 1}, fields=["rounded_total"]
		)
		self.assertEqual(len(payload["rows"]), 1)
		row = payload["rows"][0]
		self.assertEqual((row["company_code"], row["division_code"]), ("LE-TEST1", "DV-TEST1"))
		self.assertEqual(row["headcount"], len(slips))
		self.assertEqual(row["take_home"], sum(round(s.rounded_total) for s in slips))
		self.assertEqual(payload["month"], str(dates.start_date)[:7])

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

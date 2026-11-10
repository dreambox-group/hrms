# Copyright (c) 2026, Dreambox and contributors
# See license.txt

from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.parse import unquote

from PIL import Image

import frappe

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.api import get_hr_settings
from hrms.api.reimbursements import (
	DreaFinanceError,
	cancel_reimbursement,
	get_my_reimbursements,
	get_reimbursement,
	get_reimbursement_options,
	submit_reimbursement,
)
from hrms.tests.test_drea_finance import FinanceStandIns
from hrms.tests.utils import HRMSTestSuite

USER = "reimburse.staff@example.com"
URL = "https://finance.example.invalid"
REQUEST = "hrms.api.reimbursements.requests.request"


def png() -> bytes:
	out = BytesIO()
	Image.new("RGB", (4, 4), "white").save(out, format="PNG")
	return out.getvalue()


def answer(status=200, body=None):
	response = MagicMock()
	response.ok = 200 <= status < 300
	response.status_code = status
	response.json.return_value = body if body is not None else {}
	return response


class TestReimbursements(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		self.employee = frappe.db.get_value("Employee", {"user_id": USER}) or make_employee(
			USER, "_Test Company"
		)
		frappe.db.set_value("Employee", self.employee, "employee_name", "Rani Contoh")
		frappe.db.set_value(
			"Employee",
			self.employee,
			{
				"bank_name": "BCA",
				"bank_ac_no": "1234567890",
				"bank_account_name": "Rani Contoh",
				"npwp_number": "0",
			},
		)
		settings = frappe.get_single("HR Settings")
		settings.drea_finance_url = URL + "/"
		settings.drea_finance_api_key = "test-key"
		settings.show_reimbursements_in_employee_app = 1
		settings.save()
		frappe.set_user(USER)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_on_only_once_connected(self):
		self.assertTrue(get_hr_settings()["show_reimbursements"])
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "drea_finance_url", "")
		frappe.set_user(USER)
		self.assertFalse(get_hr_settings()["show_reimbursements"])
		self.assertRaises(DreaFinanceError, get_my_reimbursements)

	def test_calls_as_the_signed_in_employee(self):
		with patch(REQUEST, return_value=answer(body={"items": [], "has_more": False})) as request:
			get_my_reimbursements(start=20, limit=500, tab="waiting")
		method, url = request.call_args.args
		kwargs = request.call_args.kwargs
		self.assertEqual((method, url), ("GET", f"{URL}/api/v2/integrations/hr/reimbursements"))
		self.assertEqual(kwargs["params"], {"start": 20, "limit": 50, "tab": "waiting"})
		self.assertEqual(kwargs["headers"]["X-API-Key"], "test-key")
		self.assertEqual(kwargs["headers"]["X-Employee-Email"], USER)
		self.assertEqual(unquote(kwargs["headers"]["X-Employee-Name"]), "Rani Contoh")

	def test_options_start_from_hr_bank_details(self):
		body = {"categories": [], "last_payee": None}
		with patch(REQUEST, return_value=answer(body=body)):
			options = get_reimbursement_options()
		self.assertEqual(
			options["prefill"],
			{
				"payee_account_name": "Rani Contoh",
				"account_provider": "BCA",
				"account_number": "1234567890",
				"payee_tax_id": "0",
			},
		)
		# their last claim's account wins, as in Drea Finance
		body["last_payee"] = {
			"payee_account_name": "Rani C",
			"account_provider": "Mandiri",
			"account_number": "999",
			"payee_tax_id": "12",
		}
		with patch(REQUEST, return_value=answer(body=body)):
			self.assertEqual(get_reimbursement_options()["prefill"]["account_provider"], "Mandiri")

	def test_submit_sends_the_files_and_removes_the_copies(self):
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "struk.png", "content": png(), "is_private": 1}
		).insert()
		with patch(REQUEST, return_value=answer(201, {"ok": True, "id": "abc", "code": "EXP-1"})) as request:
			result = submit_reimbursement(
				{"description": "Taxi", "amount": "150000", "notes": "", "project_id": "not passed on"},
				[{"file_url": file_doc.file_url, "category": "receipt"}],
			)
		self.assertEqual(result["code"], "EXP-1")
		kwargs = request.call_args.kwargs
		self.assertEqual(kwargs["data"], {"description": "Taxi", "amount": "150000"})
		self.assertEqual([part[0] for part in kwargs["files"]], ["file", "file_category"])
		self.assertEqual(kwargs["files"][0][1][0], "struk.png")
		self.assertFalse(frappe.db.exists("File", file_doc.name))

	def test_a_refusal_keeps_the_files_and_says_what_is_missing(self):
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "struk.png", "content": png(), "is_private": 1}
		).insert()
		refusal = answer(422, {"error": "This cannot be sent yet.", "missing": ["NPWP/NIK"], "errors": []})
		with patch(REQUEST, return_value=refusal):
			with self.assertRaises(DreaFinanceError) as raised:
				submit_reimbursement(
					{"description": "Taxi"}, [{"file_url": file_doc.file_url, "category": "receipt"}]
				)
		self.assertIn("NPWP/NIK", str(raised.exception))
		self.assertTrue(frappe.db.exists("File", file_doc.name))

	def test_someone_elses_file_is_refused(self):
		frappe.set_user("Administrator")
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "other.png", "content": png(), "is_private": 1}
		).insert()
		frappe.set_user(USER)
		with patch(REQUEST) as request:
			self.assertRaises(
				frappe.PermissionError,
				submit_reimbursement,
				{"description": "Taxi"},
				[{"file_url": file_doc.file_url, "category": "receipt"}],
			)
		request.assert_not_called()

	def test_a_bad_key_is_not_the_employees_problem(self):
		with patch(REQUEST, return_value=answer(401, {"error": "Not authorised."})):
			with self.assertRaises(DreaFinanceError) as raised:
				cancel_reimbursement("abc", "wrong amount")
		self.assertIn("Ask HR", str(raised.exception))

	def test_switched_off_hides_it_refuses_every_call_and_keeps_the_files(self):
		"""HR Settings "Show Reimbursements in Drea One" off (production HRIS, owner 10 Nov 2026)."""
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "struk.png", "content": png(), "is_private": 1}
		).insert()
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "show_reimbursements_in_employee_app", 0)
		role_before = frappe.db.get_value("User", USER, ["drea_finance_role", "drea_finance_active"])
		frappe.set_user(USER)
		try:
			self.assertFalse(get_hr_settings()["show_reimbursements"])
			actions = [
				get_reimbursement_options,
				get_my_reimbursements,
				lambda: get_reimbursement("abc"),
				lambda: cancel_reimbursement("abc", "wrong amount"),
				lambda: submit_reimbursement(
					{"description": "Taxi", "amount": "150000"},
					[{"file_url": file_doc.file_url, "category": "receipt"}],
				),
			]
			with patch(REQUEST) as request:
				for action in actions:
					with self.assertRaises(DreaFinanceError) as raised:
						action()
					self.assertIn("aren't available in Drea One", str(raised.exception))
			request.assert_not_called()
			self.assertTrue(frappe.db.exists("File", file_doc.name))
			self.assertEqual(
				frappe.db.get_value("User", USER, ["drea_finance_role", "drea_finance_active"]), role_before
			)
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_single_value("HR Settings", "show_reimbursements_in_employee_app", 1)
			frappe.set_user(USER)

		# Ticked again: shown, and calls go through from the next one.
		self.assertTrue(get_hr_settings()["show_reimbursements"])
		with patch(REQUEST, return_value=answer(body={"items": [], "has_more": False})) as request:
			get_my_reimbursements()
		request.assert_called_once()

	def test_paused_says_so_calls_nobody_and_keeps_the_files(self):
		"""HR Settings "Pause Reimbursements" (owner, 9 Nov 2026): the cutover window."""
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": "struk.png", "content": png(), "is_private": 1}
		).insert()
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "drea_finance_paused", 1)
		role_before = frappe.db.get_value("User", USER, ["drea_finance_role", "drea_finance_active"])
		frappe.set_user(USER)
		try:
			actions = [
				get_reimbursement_options,
				get_my_reimbursements,
				lambda: get_reimbursement("abc"),
				lambda: cancel_reimbursement("abc", "wrong amount"),
				lambda: submit_reimbursement(
					{"description": "Taxi", "amount": "150000"},
					[{"file_url": file_doc.file_url, "category": "receipt"}],
				),
			]
			with patch(REQUEST) as request:
				for action in actions:
					with self.assertRaises(DreaFinanceError) as raised:
						action()
					self.assertIn("Drea Finance is moving", str(raised.exception))
			request.assert_not_called()
			self.assertTrue(frappe.db.exists("File", file_doc.name))
			self.assertEqual(
				frappe.db.get_value("User", USER, ["drea_finance_role", "drea_finance_active"]), role_before
			)
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_single_value("HR Settings", "drea_finance_paused", 0)
			frappe.set_user(USER)

		# Unticked: back to normal from the next call.
		with patch(REQUEST, return_value=answer(body={"items": [], "has_more": False})) as request:
			get_my_reimbursements()
		request.assert_called_once()


class TestFinanceAccessOnFirstCall(HRMSTestSuite):
	"""Finance no longer opens an account on the first claim: the Frappe user gets the Finance role here."""

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.get_value("Employee", {"user_id": USER}):
			make_employee(USER, "_Test Company")
		settings = frappe.get_single("HR Settings")
		settings.drea_finance_url = URL
		settings.drea_finance_api_key = "test-key"
		settings.show_reimbursements_in_employee_app = 1
		settings.save()
		frappe.db.set_value("User", USER, {"drea_finance_role": None, "drea_finance_active": 1})
		frappe.set_user(USER)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_first_call_gives_the_staff_role(self):
		with patch(REQUEST, return_value=answer(body={"items": [], "has_more": False})):
			get_my_reimbursements()
		self.assertEqual(frappe.db.get_value("User", USER, "drea_finance_role"), "staff")
		self.assertEqual(frappe.db.get_value("User", USER, "drea_finance_active"), 1)

	def test_an_existing_role_is_kept(self):
		frappe.db.set_value("User", USER, "drea_finance_role", "dept_head")
		with patch(REQUEST, return_value=answer(body={"items": [], "has_more": False})):
			get_my_reimbursements()
		self.assertEqual(frappe.db.get_value("User", USER, "drea_finance_role"), "dept_head")


class TestFirstCallOnlyOnce(FinanceStandIns, HRMSTestSuite):
	"""Audit H1: the first-claim grant never brings back a role someone cleared or switched off."""

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.get_value("Employee", {"user_id": USER}):
			make_employee(USER, "_Test Company")
		settings = frappe.get_single("HR Settings")
		settings.drea_finance_url = URL
		settings.drea_finance_api_key = "test-key"
		settings.show_reimbursements_in_employee_app = 1
		settings.save()

	def tearDown(self):
		frappe.set_user("Administrator")

	def first_call(self, role, active):
		frappe.set_user("Administrator")
		frappe.db.set_value("User", USER, {"drea_finance_role": role, "drea_finance_active": active})
		frappe.set_user(USER)
		with patch(REQUEST, return_value=answer(body={"items": [], "has_more": False})):
			get_my_reimbursements()
		return frappe.db.get_value("User", USER, ["drea_finance_role", "drea_finance_active"])

	def test_switched_off_is_not_switched_back_on(self):
		role, active = self.first_call("", 0)
		self.assertFalse(role)
		self.assertEqual(active, 0)

	def test_a_cleared_role_stays_cleared_once_finance_has_the_account(self):
		self.make_finance_tables()
		self.finance_user(USER)
		for cleared in ("", None):
			role, _active = self.first_call(cleared, 1)
			self.assertFalse(role)

	def test_never_had_an_account_still_gets_staff(self):
		self.make_finance_tables()
		role, active = self.first_call("", 1)
		self.assertEqual((role, active), ("staff", 1))

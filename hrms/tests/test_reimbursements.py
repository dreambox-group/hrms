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
	get_reimbursement_options,
	submit_reimbursement,
)
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
		self.employee = frappe.db.get_value("Employee", {"user_id": USER}) or make_employee(USER, "_Test Company")
		frappe.db.set_value("Employee", self.employee, "employee_name", "Rani Contoh")
		frappe.db.set_value(
			"Employee",
			self.employee,
			{"bank_name": "BCA", "bank_ac_no": "1234567890", "bank_account_name": "Rani Contoh", "npwp_number": "0"},
		)
		settings = frappe.get_single("HR Settings")
		settings.drea_finance_url = URL + "/"
		settings.drea_finance_api_key = "test-key"
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
			{"payee_account_name": "Rani Contoh", "account_provider": "BCA", "account_number": "1234567890", "payee_tax_id": "0"},
		)
		# their last claim's account wins, as in Drea Finance
		body["last_payee"] = {"payee_account_name": "Rani C", "account_provider": "Mandiri", "account_number": "999", "payee_tax_id": "12"}
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
				submit_reimbursement({"description": "Taxi"}, [{"file_url": file_doc.file_url, "category": "receipt"}])
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

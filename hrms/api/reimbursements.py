# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Reimbursement in the employee app: claims go to Drea Finance, not to Frappe's Expense Claim.

The app talks to these methods only; they call Drea Finance's HR endpoints
(/api/v2/integrations/hr/reimbursements) with the key from HR Settings, as the signed-in
employee (their login email). The key never reaches the browser. Drea Finance makes a Staff
account for an employee on their first claim, files it with no project for Finance to place,
and keeps the approvals and payment; this side only sends and reads.
"""

import mimetypes
from urllib.parse import quote

import requests

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.password import get_decrypted_password

from hrms.api import get_current_employee

TIMEOUT = 45
BASE_PATH = "/api/v2/integrations/hr/reimbursements"


class DreaFinanceError(frappe.ValidationError):
	pass


def connection() -> tuple[str, str]:
	url = (frappe.db.get_single_value("HR Settings", "drea_finance_url") or "").strip().rstrip("/")
	key = get_decrypted_password("HR Settings", "HR Settings", "drea_finance_api_key", raise_exception=False)
	if not url or not key:
		frappe.throw(_("Reimbursement isn't connected to Drea Finance yet. Ask HR."), DreaFinanceError)
	return url, key


def headers(key: str) -> dict:
	user = frappe.session.user
	email = frappe.db.get_value("User", user, "email") or user
	employee = get_current_employee()
	name = frappe.db.get_value("Employee", employee, "employee_name") if employee else ""
	return {
		"X-API-Key": key,
		"X-Employee-Email": email,
		"X-Employee-Name": quote(name or ""),
		"Accept": "application/json",
	}


def call(method: str, path: str, **kwargs) -> dict:
	"""One call to Drea Finance as the signed-in employee; its refusal is shown as it says it."""
	url, key = connection()
	try:
		response = requests.request(method, f"{url}{BASE_PATH}{path}", headers=headers(key), timeout=TIMEOUT, **kwargs)
	except requests.RequestException:
		frappe.log_error("Drea Finance unreachable", reference_doctype="HR Settings")
		frappe.throw(_("Drea Finance can't be reached right now. Try again in a moment."), DreaFinanceError)

	try:
		body = response.json()
	except ValueError:
		body = {}
	if response.ok:
		return body

	if response.status_code in (401, 503):
		# the key or the setup, which the employee can do nothing about
		frappe.log_error(f"Drea Finance refused the key ({response.status_code}): {body.get('error')}", reference_doctype="HR Settings")
		frappe.throw(_("Drea Finance refused the connection. Ask HR to check the Drea Finance settings."), DreaFinanceError)
	problems = [*body.get("missing", []), *body.get("errors", [])]
	message = body.get("error") or _("Drea Finance could not do that.")
	if body.get("missing"):
		message = _("Fill in: {0}").format(", ".join(body["missing"]))
		if body.get("errors"):
			message += ". " + " ".join(body["errors"])
	elif problems:
		message = " ".join(problems)
	frappe.throw(message, DreaFinanceError, title=_("Not sent"))


@frappe.whitelist()
def get_reimbursement_options() -> dict:
	"""The form's choices and words from Drea Finance, and bank details to start from."""
	employee = get_current_employee()
	options = call("GET", "/options")
	bank = frappe.db.get_value(
		"Employee",
		employee,
		["employee_name", "bank_name", "bank_ac_no", "bank_account_name", "npwp_number", "ktp_number"],
		as_dict=True,
	) if employee else None
	last = options.get("last_payee") or {}
	# their last claim's account first (as in Drea Finance), then what HR has on file
	options["prefill"] = {
		"payee_account_name": last.get("payee_account_name") or (bank and (bank.bank_account_name or bank.employee_name)) or "",
		"account_provider": last.get("account_provider") or (bank and bank.bank_name) or "",
		"account_number": last.get("account_number") or (bank and bank.bank_ac_no) or "",
		"payee_tax_id": last.get("payee_tax_id") or (bank and (bank.npwp_number or bank.ktp_number)) or "",
	}
	return options


@frappe.whitelist()
def get_my_reimbursements(start: int = 0, limit: int = 20, tab: str | None = None) -> dict:
	"""The employee's claims, newest first; `tab` (waiting, done, stopped) is filtered by Drea Finance."""
	get_current_employee()
	params = {"start": max(cint(start), 0), "limit": min(max(cint(limit) or 20, 1), 50)}
	if tab in ("waiting", "done", "stopped"):
		params["tab"] = tab
	return call("GET", "", params=params)


@frappe.whitelist()
def get_reimbursement(name: str) -> dict:
	get_current_employee()
	return call("GET", f"/{quote(name, safe='')}")


@frappe.whitelist(methods=["POST"])
def submit_reimbursement(fields: dict | str, files: list | str) -> dict:
	"""Send a claim with its proof. The files were uploaded to this site by the employee
	(private); they are sent on to Drea Finance and removed here once it has them."""
	get_current_employee()
	fields = frappe.parse_json(fields) if isinstance(fields, str) else fields
	files = frappe.parse_json(files) if isinstance(files, str) else files
	if not files:
		frappe.throw(_("Add the proof of the expense (invoice/receipt)."))
	if len(files) > 10:
		frappe.throw(_("Send at most 10 files with one claim."))

	file_docs, parts = [], []
	for row in files:
		file_doc = frappe.get_doc("File", {"file_url": row.get("file_url")})
		if file_doc.owner != frappe.session.user or file_doc.attached_to_doctype:
			frappe.throw(_("That file isn't one of yours."), frappe.PermissionError)
		content = file_doc.get_content()
		if isinstance(content, str):
			content = content.encode()
		mime = mimetypes.guess_type(file_doc.file_name or "")[0] or "application/octet-stream"
		parts.append(("file", (file_doc.file_name, content, mime)))
		parts.append(("file_category", (None, row.get("category") or "")))
		file_docs.append(file_doc)

	data = {
		key: str(value)
		for key, value in (fields or {}).items()
		if key
		in (
			"expense_category",
			"description",
			"notes",
			"amount",
			"expense_date",
			"cost_responsibility",
			"payee_account_name",
			"account_number",
			"account_provider",
			"payee_tax_id",
		)
		and value not in (None, "")
	}
	result = call("POST", "", data=data, files=parts)

	# Drea Finance keeps the proof now; the copies here were only on their way
	for file_doc in file_docs:
		file_doc.delete(ignore_permissions=True)
	return result


@frappe.whitelist(methods=["POST"])
def cancel_reimbursement(name: str, reason: str | None = None) -> dict:
	get_current_employee()
	return call("POST", f"/{quote(name, safe='')}/cancel", json={"reason": (reason or "").strip() or None})

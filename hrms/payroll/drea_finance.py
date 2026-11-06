# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Payroll totals to Drea Finance (Drea Finance's handbook HR-PAYROLL-LINK.md, 27 Oct 2026).

When HR submits a Payroll Entry's salary slips, Drea Finance gets ONE message for the entry:
totals per company and division (headcount, amount per pay code, take-home pay). No name,
employee id, NIK, NPWP, bank account or per-person figure ever leaves this module, and Drea
Finance refuses any field it does not list, so none can slip in. Each person's slip stays here.

Where things live:
- HR Settings: drea_finance_url + drea_finance_api_key (shared with reimbursements),
  drea_finance_send_payroll (the switch) and drea_finance_payroll_test_only (every send is a dry run);
- Company.drea_finance_code, Department.drea_finance_division (hrms.finance);
- Salary Component.drea_finance_component and the Payroll Entry fields below (hrms.setup).

A send that cannot be built (a missing code, take-home that does not add up) is never guessed
at: it stops, and the reason is written on the Payroll Entry for HR to read.
"""

import hashlib
import json
import time

import requests

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate
from frappe.utils.password import get_decrypted_password

PATH = "/api/v2/integrations/payroll"
TIMEOUT = 30
RETRY_WAITS = (5, 20)  # after the first try: at most three tries, only on a network error or 5xx

# Drea Finance's pay codes and what each is (GET /api/v2/integrations/payroll/reference).
# Finance can add codes in its Settings -> Salary; add them here too (and to the Select options).
CODE_KINDS = {
	"SALARY": "earning",
	"INCENTIVE": "earning",
	"PPH21_WITHHELD": "deduction",
	"BPJS_KES_EMPLOYEE": "deduction",
	"BPJS_TK_EMPLOYEE": "deduction",
	"OVERPAID_RECOVERY": "deduction",
	"BPJS_KES_COMPANY": "employer",
	"BPJS_TK_COMPANY": "employer",
	"PPH21_COMPANY": "employer",
}
COMPONENT_OPTIONS = "\n" + "\n".join(CODE_KINDS)

# which codes a Salary Component of each type may carry
ALLOWED_KINDS = {
	"Earning": {"earning"},
	# a cut the company keeps (late penalty, unpaid leave) reduces the earning it is mapped to
	"Deduction": {"earning", "deduction"},
	"Employer Contribution": {"employer"},
}
TABLE_TYPE = {
	"earnings": "Earning",
	"deductions": "Deduction",
	"employer_contributions": "Employer Contribution",
}


class PayrollSendError(frappe.ValidationError):
	pass


# --- Salary Component -------------------------------------------------------------------------


def validate_component(doc, method=None):
	"""doc_event: a component's Drea Finance code must fit its type."""
	code = doc.get("drea_finance_component")
	if not code:
		return
	kind = CODE_KINDS.get(code)
	allowed = ALLOWED_KINDS.get(doc.type, set())
	if kind not in allowed:
		frappe.throw(
			_("{0} is a {1} code in Drea Finance; a {2} component can't use it.").format(
				frappe.bold(code), kind or _("unknown"), _(doc.type)
			),
			title=_("Drea Finance code"),
		)


# --- building the message -----------------------------------------------------------------------


def summarise(slips, lines_by_slip, company_code, division_code, components, use_net_pay):
	"""The rows of the message, from plain data (kept apart from the database so it can be tested).

	slips: dicts with name, company, department, net_pay, rounded_total.
	lines_by_slip: {slip name: [dicts with parentfield, salary_component, amount,
	    statistical_component, do_not_include_in_total]}.
	company_code / division_code: {company: LE code}, {department: DV code}.
	components: {component name: Drea Finance code or None}.
	Raises PayrollSendError listing every problem at once."""
	problems = []
	rows = {}
	for s in slips:
		company = company_code.get(s["company"])
		division = division_code.get(s["department"]) if s.get("department") else None
		if not company:
			problems.append(_("Company {0} has no Drea Finance code.").format(s["company"]))
		if not s.get("department"):
			problems.append(_("Salary Slip {0} has no department.").format(s["name"]))
		elif not division:
			problems.append(_("Department {0} has no Drea Finance division.").format(s["department"]))
		if not company or not division:
			continue
		row = rows.setdefault(
			(company, division),
			{
				"company_code": company,
				"division_code": division,
				"headcount": 0,
				"amounts": {},
				"take_home": 0,
			},
		)
		row["headcount"] += 1
		row["take_home"] += round(flt(s["net_pay"] if use_net_pay else s["rounded_total"]))
		for line in lines_by_slip.get(s["name"], []):
			if (
				line.get("statistical_component")
				or line.get("do_not_include_in_total")
				or not flt(line["amount"])
			):
				continue
			code = components.get(line["salary_component"])
			if not code:
				if line["parentfield"] == "employer_contributions":
					continue  # not sent until HR maps it; take-home doesn't depend on it
				problems.append(
					_("Salary Component {0} has no Drea Finance code.").format(line["salary_component"])
				)
				continue
			kind = CODE_KINDS.get(code)
			if kind not in ALLOWED_KINDS.get(TABLE_TYPE.get(line["parentfield"]), set()):
				problems.append(
					_("Salary Component {0} sits in {1} but its code {2} is a {3} code.").format(
						line["salary_component"], line["parentfield"], code, kind or _("unknown")
					)
				)
				continue
			amount = round(flt(line["amount"]))
			if line["parentfield"] == "deductions" and kind == "earning":
				amount = -amount  # a cut the company keeps, e.g. the late penalty
			row["amounts"][code] = row["amounts"].get(code, 0) + amount

	for row in rows.values():
		row["amounts"] = {k: v for k, v in sorted(row["amounts"].items()) if v}
		expected = sum(
			v * (1 if CODE_KINDS[k] == "earning" else -1)
			for k, v in row["amounts"].items()
			if CODE_KINDS[k] != "employer"
		)
		if expected != row["take_home"]:
			problems.append(
				_(
					"{0} / {1}: take-home is {2} but the earnings less the deductions come to {3}. "
					"Check rounding (Round to the Nearest Integer on the components) and the mappings."
				).format(row["company_code"], row["division_code"], row["take_home"], expected)
			)
	if problems:
		raise PayrollSendError("\n".join(dict.fromkeys(problems)))
	return sorted(rows.values(), key=lambda r: (r["company_code"], r["division_code"]))


def build_payload(pe) -> dict:
	slips = frappe.get_all(
		"Salary Slip",
		filters={"payroll_entry": pe.name, "docstatus": 1},
		fields=["name", "company", "department", "net_pay", "rounded_total"],
	)
	if not slips:
		raise PayrollSendError(_("No submitted salary slips to send."))
	lines = frappe.get_all(
		"Salary Detail",
		filters={"parenttype": "Salary Slip", "parent": ["in", [s.name for s in slips]]},
		fields=[
			"parent",
			"parentfield",
			"salary_component",
			"amount",
			"statistical_component",
			"do_not_include_in_total",
		],
	)
	lines_by_slip = {}
	for line in lines:
		lines_by_slip.setdefault(line.parent, []).append(line)
	rows = summarise(
		slips,
		lines_by_slip,
		dict(frappe.get_all("Company", fields=["name", "drea_finance_code"], as_list=True)),
		dict(frappe.get_all("Department", fields=["name", "drea_finance_division"], as_list=True)),
		dict(frappe.get_all("Salary Component", fields=["name", "drea_finance_component"], as_list=True)),
		use_net_pay=cint(frappe.db.get_single_value("Payroll Settings", "disable_rounded_total")),
	)
	start = getdate(pe.start_date)
	return {
		"month": f"{start.year}-{start.month:02d}",
		"kind": (pe.get("drea_finance_kind") or "Salary").lower(),
		"pay_date": str(getdate(pe.posting_date)),
		"rows": rows,
	}


def figures_hash(payload: dict) -> str:
	figures = [payload["month"], payload["kind"], payload["pay_date"], payload["rows"]]
	return hashlib.sha256(json.dumps(figures, sort_keys=True).encode()).hexdigest()


def run_history(pe) -> tuple[str, int, str | None]:
	"""(run id, last version sent, its hash) for this entry and the entries it amends.

	The run id is the first entry's name, so an amended entry continues the same run. The Drea
	Finance fields are no_copy, so a duplicated (not amended) entry starts a run of its own."""
	chain = [pe.name]
	previous = pe.get("amended_from")
	while previous and previous not in chain:
		chain.append(previous)
		previous = frappe.db.get_value("Payroll Entry", previous, "amended_from")
	sent = frappe.get_all(
		"Payroll Entry",
		filters={"name": ["in", chain], "drea_finance_version": [">", 0]},
		fields=["drea_finance_version", "drea_finance_hash"],
		order_by="drea_finance_version desc",
		limit=1,
	)
	if sent:
		return chain[-1], cint(sent[0].drea_finance_version), sent[0].drea_finance_hash
	return chain[-1], 0, None


def next_version(last_version: int, last_hash: str | None, new_hash: str) -> int:
	"""The same figures keep their version (Finance answers 'unchanged'); new figures get the next."""
	if not last_version:
		return 1
	return last_version if last_hash == new_hash else last_version + 1


# --- sending ------------------------------------------------------------------------------------


def settings() -> dict:
	hr = frappe.get_cached_doc("HR Settings")
	return {
		"url": (hr.get("drea_finance_url") or "").strip().rstrip("/"),
		"key": get_decrypted_password(
			"HR Settings", "HR Settings", "drea_finance_api_key", raise_exception=False
		),
		"enabled": cint(hr.get("drea_finance_send_payroll")),
		"test_only": cint(hr.get("drea_finance_payroll_test_only")),
	}


def post(url: str, key: str, payload: dict):
	"""POST with at most three tries; retries only a network error or a 5xx (a 4xx needs a person)."""
	waits = list(RETRY_WAITS)
	while True:
		try:
			response = requests.post(
				url + PATH,
				json=payload,
				headers={"X-API-Key": key, "Accept": "application/json"},
				timeout=TIMEOUT,
			)
			if response.status_code < 500 or not waits:
				return response
		except requests.RequestException:
			if not waits:
				raise
		time.sleep(waits.pop(0))


def describe(response) -> tuple[dict, str]:
	try:
		body = response.json()
	except ValueError:
		body = {}
	message = body.get("message") or body.get("error") or (response.text or "")[:300]
	if body.get("problems"):
		message += "\n" + "\n".join(f"- {p}" for p in body["problems"])
	return body, message


def send(payroll_entry: str, test: bool = False, automatic: bool = False) -> dict:
	"""Build and send one Payroll Entry. Writes the outcome on the entry and returns it."""
	pe = frappe.get_doc("Payroll Entry", payroll_entry)
	conf = settings()
	if automatic and not conf["enabled"]:
		return {"status": "off"}
	stamp = frappe.utils.now_datetime().strftime("%d-%m-%Y %H:%M")

	def note(text):
		pe.db_set("drea_finance_status", f"{stamp}: {text}", update_modified=False)

	if not conf["url"] or not conf["key"]:
		note(_("Not sent: Drea Finance's URL or key is missing in HR Settings."))
		raise PayrollSendError(_("Drea Finance's URL or key is missing in HR Settings."))
	try:
		payload = build_payload(pe)
	except PayrollSendError as e:
		note(_("Not sent: {0}").format(e))
		raise

	new_hash = figures_hash(payload)
	run_id, last_version, last_hash = run_history(pe)
	version = next_version(last_version, last_hash, new_hash)
	dry_run = bool(test or conf["test_only"])
	payload = {"hr_run_id": run_id, "version": version, "dry_run": dry_run, **payload}

	try:
		response = post(conf["url"], conf["key"], payload)
	except requests.RequestException:
		note(
			_(
				"Not sent: Drea Finance could not be reached (tried three times). Use Send to Drea Finance later."
			)
		)
		frappe.log_error(
			"Drea Finance payroll: unreachable", reference_doctype="Payroll Entry", reference_name=pe.name
		)
		raise PayrollSendError(_("Drea Finance could not be reached. Try again later."))

	body, message = describe(response)
	label = _("Test") if dry_run else _("Version {0}").format(version)
	if response.ok and not dry_run:
		pe.db_set(
			{"drea_finance_run_id": run_id, "drea_finance_version": version, "drea_finance_hash": new_hash},
			update_modified=False,
		)
	if response.ok:
		totals = (body.get("summary") or {}).get("totals") or {}
		extra = (
			_(" ({0} people, take-home {1})").format(totals.get("people"), totals.get("take_home"))
			if totals
			else ""
		)
		note(f"{label}: {body.get('status') or response.status_code}. {message}{extra}")
	else:
		note(_("{0} refused ({1}): {2}").format(label, response.status_code, message))
		if response.status_code >= 500:
			frappe.log_error(
				"Drea Finance payroll: server error",
				message,
				reference_doctype="Payroll Entry",
				reference_name=pe.name,
			)
	return {
		"ok": response.ok,
		"status_code": response.status_code,
		"status": body.get("status"),
		"message": message,
		"dry_run": dry_run,
		"version": version,
	}


def send_in_background(payroll_entry: str):
	"""Queued after a Payroll Entry's slips are submitted; a failure is written on the entry, never raised
	into the submission."""
	try:
		send(payroll_entry, automatic=True)
		frappe.db.commit()  # nosemgrep: the outcome is the job's whole result
	except PayrollSendError:
		frappe.db.commit()  # nosemgrep: keep the note written on the entry
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			"Drea Finance payroll: send failed",
			reference_doctype="Payroll Entry",
			reference_name=payroll_entry,
		)


def queue_after_submission(payroll_entry: str):
	"""Called from submit_salary_slips_for_employees once the slips are submitted."""
	if not cint(frappe.db.get_single_value("HR Settings", "drea_finance_send_payroll")):
		return
	frappe.enqueue(
		"hrms.payroll.drea_finance.send_in_background",
		payroll_entry=payroll_entry,
		queue="default",
		enqueue_after_commit=True,
		job_id=f"drea_finance_payroll::{payroll_entry}",
		deduplicate=True,
	)


@frappe.whitelist()
def send_to_drea_finance(payroll_entry: str, test: int = 0):
	"""The 'Drea Finance' buttons on a submitted Payroll Entry."""
	frappe.only_for(("HR Manager", "HR User", "System Manager"))
	pe = frappe.get_doc("Payroll Entry", payroll_entry)
	pe.check_permission("read")
	if pe.docstatus != 1 or not pe.salary_slips_submitted:
		frappe.throw(_("Submit the salary slips first."))
	if not cint(test) and not settings()["enabled"]:
		frappe.throw(_("Sending payroll to Drea Finance is off. Turn it on in HR Settings, or use Test."))
	try:
		return send(payroll_entry, test=bool(cint(test)))
	except PayrollSendError as e:
		frappe.db.commit()  # nosemgrep: keep the note on the entry for HR to read
		frappe.throw(str(e), title=_("Not sent to Drea Finance"))

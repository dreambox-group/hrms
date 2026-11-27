# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Load HR's pay sheet (owner, 27 Nov 2026): each person's PTKP status and monthly pay, from the
sheet HR keeps ("Data Karyawan dan Payroll": No, Employee Number, Name, Status Kawin, Basic
Salary). Dry run first; it prints every change and saves nothing:

    bench --site <site> execute hrms.payroll.drea_pay_sheet.load \\
        --kwargs "{'path': '/path/to/sheet.xlsx', 'from_date': '2026-10-19'}"
    ... --kwargs "{'path': ..., 'from_date': ..., 'dry_run': False}"

- Status Kawin: "Belum Menikah" is TK/0 (no dependants given), "Menikah, K/1" is K/1; a plain
  PTKP status (TK/1, K/2) is taken as it is. Written to Employee > PTKP Status.
- Basic Salary: the amount the person receives. A number becomes a Salary Structure Assignment
  from from_date (or their joining date, if later) on the structure for their employment type:
  Drea Full-time (permanent and contract) or Drea Intern. "PRIVE": a partner paid by drawing
  (hrms.payroll.drea_payroll_setup.add_leader), on their own leader structure with base
  prive_amount until HR enters the real figure. Empty: not on payroll (freelancers invoice).
- A draft structure must be submitted first; submit_structures=True does it (HR's check of the
  drafts comes first on production).
"""

import re

import frappe
from frappe.utils import cint, flt, getdate

from hrms.payroll import drea_payroll_setup as setup

STRUCTURE_FOR = {
	"Full-time Permanent": "Drea Full-time - {abbr}",
	"Full-time Contract": "Drea Full-time - {abbr}",
	"Intern": "Drea Intern - {abbr}",
}
PRIVE = "PRIVE"


def ptkp_from(text) -> str | None:
	text = re.sub(r"\s+", "", str(text or "")).upper()
	if not text:
		return None
	if found := re.search(r"(TK|K)/[0-3]", text):
		return found.group(0)
	if text.startswith("BELUMMENIKAH") or text in ("SINGLE", "TIDAKKAWIN"):
		return "TK/0"
	if text.startswith("MENIKAH") or text == "KAWIN":
		return "K/0"
	return None


def prive_code_for(employee_name: str) -> str:
	first = re.sub(r"[^A-Z0-9]", "", (employee_name or "").split()[0].upper()) if employee_name else ""
	return f"PRIVE_{first}"


def read_sheet(path) -> list[dict]:
	from openpyxl import load_workbook

	ws = load_workbook(path, data_only=True, read_only=True).worksheets[0]
	rows, header = [], None
	for values in ws.iter_rows(values_only=True):
		cells = [str(v).strip().lower() if v is not None else "" for v in values]
		if header is None:
			if "employee number" in cells:
				header = {name: cells.index(name) for name in cells if name}
			continue
		get = lambda name, values=values: values[header[name]] if name in header else None  # noqa: E731
		if get("employee number") in (None, ""):
			continue
		rows.append(
			{
				"employee": str(get("employee number")).strip(),
				"name": (get("name") or "").strip(),
				"status": get("status kawin"),
				"basic": get("basic salary"),
			}
		)
	if header is None:
		frappe.throw("The sheet has no 'Employee Number' column.")
	return rows


def load(
	path,
	from_date,
	dry_run=True,
	prive_amount=10_000_000,
	submit_structures=False,
	commit=True,
):
	dry_run = dry_run not in (False, 0, "0", "false", "False")
	submit_structures = submit_structures not in (False, 0, "0", "false", "False")
	from_date = getdate(from_date)
	plan = setup.Plan(dry_run)
	skipped, submitted = [], set()

	for row in read_sheet(path):
		emp = frappe.db.get_value(
			"Employee",
			row["employee"],
			[
				"name",
				"employee_name",
				"company",
				"employment_type",
				"date_of_joining",
				"ptkp_status",
				"status",
			],
			as_dict=True,
		)
		if not emp:
			skipped.append(f"{row['employee']} {row['name']}: no such employee")
			continue
		who = f"{emp.name} {emp.employee_name}"

		ptkp = ptkp_from(row["status"])
		if not ptkp:
			skipped.append(f"{who}: status {row['status']!r} is not a PTKP status")
		elif ptkp != emp.ptkp_status:
			plan.do(
				f"{who}: PTKP Status {emp.ptkp_status or '-'} -> {ptkp}",
				lambda e=emp.name, p=ptkp: frappe.db.set_value("Employee", e, "ptkp_status", p),
			)

		basic = row["basic"]
		abbr = frappe.get_cached_value("Company", emp.company, "abbr")
		if basic in (None, ""):
			skipped.append(f"{who}: no pay in the sheet (not on payroll)")
			continue
		if str(basic).strip().upper() == PRIVE:
			code = prive_code_for(emp.employee_name)
			plan.lines.extend(
				f"{who}: {line}"
				for line in setup.add_leader(emp.name, code, dry_run=dry_run, commit=False, verbose=False)
			)
			structure = setup.LEADER_STRUCTURE.format(name=emp.employee_name, abbr=abbr)
			base = flt(prive_amount)
		else:
			template = STRUCTURE_FOR.get(emp.employment_type)
			if not template:
				skipped.append(f"{who}: {emp.employment_type} has no salary structure")
				continue
			structure = template.format(abbr=abbr)
			base = flt(basic)

		start = max(from_date, getdate(emp.date_of_joining))
		assign(plan, who, emp, structure, base, start, submit_structures, dry_run, submitted)

	if not dry_run and commit:
		frappe.db.commit()  # nosemgrep: a bench execute command, run by hand
	print(f"{'DRY RUN, nothing saved' if dry_run else 'APPLIED'}: {len(plan.lines)} change(s)")
	for line in plan.lines:
		print(" -", line)
	for line in skipped:
		print("   skipped:", line)
	return {"changes": plan.lines, "skipped": skipped}


def assign(plan, who, emp, structure, base, start, submit_structures, dry_run, submitted):
	status = frappe.db.get_value("Salary Structure", structure, "docstatus")
	if status is None and not dry_run:
		frappe.throw(f"{who}: salary structure {structure} does not exist; run the payroll setup first.")
	if status == 0 or (status is None and dry_run):
		if not submit_structures:
			frappe.throw(
				f"Salary structure {structure} is a draft: HR submits it first (or submit_structures=True)."
			)
		if structure not in submitted:
			submitted.add(structure)
			plan.do(
				f"Submit salary structure {structure}",
				lambda s=structure: frappe.get_doc("Salary Structure", s).submit(),
			)

	existing = frappe.db.get_value(
		"Salary Structure Assignment",
		{"employee": emp.name, "docstatus": 1, "from_date": start},
		["name", "salary_structure", "base"],
		as_dict=True,
	)
	if existing and existing.salary_structure == structure and flt(existing.base) == base:
		return
	if existing:
		plan.lines.append(
			f"   {who}: already assigned {existing.salary_structure} at {existing.base:,.0f} from {start}; "
			"left as it is"
		)
		return

	def create():
		frappe.get_doc(
			{
				"doctype": "Salary Structure Assignment",
				"employee": emp.name,
				"salary_structure": structure,
				"company": emp.company,
				"from_date": start,
				"base": base,
				"currency": frappe.get_cached_value("Company", emp.company, "default_currency"),
			}
		).submit()

	plan.do(f"{who}: {structure}, base {base:,.0f} from {start}", create)

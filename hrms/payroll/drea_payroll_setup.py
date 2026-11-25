# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Drea payroll setup: salary components and their accounts, a draft salary
structure per company, and leave types that do not count holidays (handover, 5 Nov 2026 audit).

Run it as a dry run first; it prints every change and saves nothing:

    bench --site <site> execute hrms.payroll.drea_payroll_setup.apply
    bench --site <site> execute hrms.payroll.drea_payroll_setup.apply --kwargs "{'dry_run': False}"

Safe to run again: what is already right is left alone. Nothing is deleted. A component that
should go is disabled, so any old structure or slip that names it still opens.

Figures HR/Finance must confirm before production are marked CONFIRM below.
"""

import frappe
from frappe.utils import flt

# --- figures -----------------------------------------------------------------------------------
# BPJS Kesehatan: 1% employee + 4% company of the wage, the wage capped at Rp12,000,000
# (Perpres 64/2020).
BPJS_KES_CAP = 12_000_000
# BPJS Ketenagakerjaan Jaminan Pensiun wage cap. It changes every March.
# CONFIRM: Rp10,547,400 is the March 2025 figure; Finance to give the current one.
JP_WAGE_CAP = 10_547_400
# JKK depends on the work's risk group; 0.24% is the lowest (office work). CONFIRM.
JKK_RATE = 0.0024

# --- the components ----------------------------------------------------------------------------
# name: (abbr, type, formula or None (amount entered per month), Drea Finance pay code (written to
#        Drea Finance Settings > Salary Components -> Pay Codes, not to the component),
#        depends on payment days, is tax applicable)
# "base" is the person's monthly base in their Salary Structure Assignment. BPJS is worked out on
# the full monthly wage, not on days worked, so it uses base, not the prorated Basic.
COMPONENTS = {
	# earnings
	"Basic": ("B", "Earning", "base", "SALARY", 1, 1),
	"Incentive": ("INC", "Earning", None, "INCENTIVE", 0, 1),
	# CONFIRM: Drea Finance has no THR code. THR is run as its own Payroll Entry with
	# Kind (Drea Finance) = THR, so the component books as SALARY.
	"THR": ("THR", "Earning", None, "SALARY", 0, 1),
	"Arrear": ("A", "Earning", None, "SALARY", 0, 1),
	"Leave Encashment": ("LE", "Earning", None, "SALARY", 1, 1),
	# deductions taken from pay
	"BPJS Kesehatan Karyawan": ("BPJSKES_K", "Deduction", f"min(base, {BPJS_KES_CAP}) * 0.01", "BPJS_KES_EMPLOYEE", 0, 0),
	"BPJS JHT Karyawan": ("JHT_K", "Deduction", "base * 0.02", "BPJS_TK_EMPLOYEE", 0, 0),
	"BPJS JP Karyawan": ("JP_K", "Deduction", f"min(base, {JP_WAGE_CAP}) * 0.01", "BPJS_TK_EMPLOYEE", 0, 0),
	# CONFIRM: PPh 21 has no formula yet, so it is 0 on every slip (see the report).
	"PPh21": ("PPh21", "Deduction", None, "PPH21_WITHHELD", 0, 0),
	# a cut the company keeps reduces salary in Finance
	"Late Penalty": ("LATE", "Deduction", "late_entry_days * 50000", "SALARY", 0, 1),
	"Unpaid Leave": ("UnLe", "Deduction", None, "SALARY", 1, 0),
	# employer contributions (company pays on top). Taxable for PPh 21: Kesehatan, JKK and JKM
	# paid by the company count as the employee's income; JHT and JP do not.
	"BPJS Kesehatan": ("BPJSKES", "Employer Contribution", f"min(base, {BPJS_KES_CAP}) * 0.04", "BPJS_KES_COMPANY", 0, 1),
	"BPJS JHT": ("JHT", "Employer Contribution", "base * 0.037", "BPJS_TK_COMPANY", 0, 0),
	"BPJS JP": ("JP", "Employer Contribution", f"min(base, {JP_WAGE_CAP}) * 0.02", "BPJS_TK_COMPANY", 0, 0),
	"BPJS JKM": ("JKM", "Employer Contribution", "base * 0.003", "BPJS_TK_COMPANY", 0, 1),
	"BPJS JKK": ("JKK", "Employer Contribution", f"base * {JKK_RATE}", "BPJS_TK_COMPANY", 0, 1),
}

# disabled, never deleted: the single 4% "BPJS" deduction (wrong rate, no split), the duplicate
# "Income Tax" (PPh21 covers it), PPh23 (a tax on payments to vendors, not on salaries) and the
# second basic pay "Gaji Pokok Denalo" (Basic does it for every company).
RETIRED = ("BPJS", "Income Tax", "PPh23", "Gaji Pokok Denalo")

# the draft structure every company with employees gets; HR checks it, then submits and assigns
STRUCTURE = {
	"earnings": ["Basic"],
	"deductions": ["BPJS Kesehatan Karyawan", "BPJS JHT Karyawan", "BPJS JP Karyawan", "PPh21", "Late Penalty"],
	"employer_contributions": ["BPJS Kesehatan", "BPJS JHT", "BPJS JP", "BPJS JKM", "BPJS JKK"],
}
STRUCTURE_NAME = "Drea Standard - {abbr}"

# leave that should not count Saturdays, Sundays and public holidays as leave days. Maternity
# and miscarriage leave stay calendar-based (the law counts them in months).
LEAVE_TYPES_WITHOUT_HOLIDAYS = ("Casual Leave", "Compensatory Off", "Leave Without Pay", "Privilege Leave", "Sick Leave")


class Plan:
	def __init__(self, dry_run):
		self.dry_run = dry_run
		self.lines = []

	def do(self, message, action):
		self.lines.append(message)
		if not self.dry_run:
			action()


def apply(dry_run=True, companies=None, commit=True):
	"""Bring components, accounts, structures and leave types in line. Returns the change list."""
	dry_run = dry_run not in (False, 0, "0", "false", "False")
	companies = companies or real_companies()
	plan = Plan(dry_run)

	for company in dict.fromkeys(root_company(c) for c in companies):
		ensure_accounts(plan, company)
	for name, spec in COMPONENTS.items():
		ensure_component(plan, name, spec, companies)
	ensure_pay_codes(plan)
	for name in RETIRED:
		if frappe.db.get_value("Salary Component", name, "disabled") == 0:
			plan.do(f"Disable component {name}", lambda n=name: frappe.db.set_value("Salary Component", n, "disabled", 1))
	for company in companies:
		if frappe.db.exists("Employee", {"company": company, "status": "Active"}):
			ensure_structure(plan, company)
	for leave_type in LEAVE_TYPES_WITHOUT_HOLIDAYS:
		if frappe.db.get_value("Leave Type", leave_type, "include_holiday") == 1:
			plan.do(
				f"Leave Type {leave_type}: stop counting holidays as leave days",
				lambda lt=leave_type: frappe.db.set_value("Leave Type", lt, "include_holiday", 0),
			)

	if not dry_run and commit:  # tests pass commit=False, so their changes roll back
		frappe.db.commit()  # nosemgrep: a bench execute command, run by hand
	header = "DRY RUN, nothing saved" if dry_run else "APPLIED"
	print(f"{header}: {len(plan.lines)} change(s)")
	for line in plan.lines:
		print(" -", line)
	return plan.lines


def real_companies():
	"""Dreambox's four CVs (the old "Dreambox" parent company is gone, drea_org_setup)."""
	return frappe.get_all("Company", pluck="name", order_by="name")


# --- accounts ----------------------------------------------------------------------------------


def accounts_for(company):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	return {
		"expense": f"Salary - {abbr}",
		"bpjs": f"BPJS Payable - {abbr}",
		"pph21": f"PPh 21 Payable - {abbr}",
		"payroll": f"Payroll Payable - {abbr}",
	}


def root_company(company):
	"""ERPNext only lets an account be added to a group's top company, which copies it to every
	company under it (the CVs sit under "Dreambox")."""
	while parent := frappe.get_cached_value("Company", company, "parent_company"):
		company = parent
	return company


def ensure_accounts(plan, company):
	names = accounts_for(company)
	payroll_payable = frappe.db.get_value("Account", names["payroll"], ["parent_account"], as_dict=True)
	for key, account_type in (("bpjs", "Payable"), ("pph21", "Tax")):
		if frappe.db.exists("Account", names[key]) or not payroll_payable:
			continue
		account_name = names[key].rsplit(" - ", 1)[0]
		below = [c for c in frappe.get_all("Company", filters={"parent_company": company}, pluck="name")]
		copied = f" (copied to {', '.join(below)})" if below else ""

		def create(account_name=account_name, account_type=account_type):
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": account_name,
					"company": company,
					"parent_account": payroll_payable.parent_account,
					"account_type": account_type,
					"root_type": "Liability",
					"report_type": "Balance Sheet",
				}
			).insert(ignore_permissions=True)

		plan.do(f"Create account {names[key]}{copied}", create)


def account_row(company, component_type, component):
	names = accounts_for(company)
	if component_type == "Earning":
		return {"company": company, "account": names["expense"]}
	if component_type == "Deduction":
		if component.startswith("BPJS"):
			return {"company": company, "account": names["bpjs"]}
		if component == "PPh21":
			return {"company": company, "account": names["pph21"]}
		# a cut the company keeps: less salary expense
		return {"company": company, "account": names["expense"]}
	# employer contribution: company cost, owed to BPJS
	return {"company": company, "account": names["expense"], "liability_account": names["bpjs"]}


# --- components --------------------------------------------------------------------------------


def ensure_component(plan, name, spec, companies):
	abbr, component_type, formula, code, payment_days, taxable = spec
	wanted = {
		"type": component_type,
		"depends_on_payment_days": payment_days,
		"is_tax_applicable": taxable,
		"amount_based_on_formula": 1 if formula else 0,
		"formula": formula or "",
		"round_to_the_nearest_integer": 1,
		"remove_if_zero_valued": 1,
		"disabled": 0,
	}
	if not frappe.db.exists("Salary Component", name):

		def create():
			doc = frappe.new_doc("Salary Component")
			doc.update({"salary_component": name, "salary_component_abbr": abbr, **wanted})
			for company in companies:
				doc.append("accounts", account_row(company, component_type, name))
			doc.insert(ignore_permissions=True)

		plan.do(f"Create component {name} ({component_type}, {code}, {formula or 'amount per month'})", create)
		return

	doc = frappe.get_doc("Salary Component", name)
	changes = {f: v for f, v in wanted.items() if normalise(doc.get(f)) != normalise(v)}
	have = {row.company for row in doc.accounts}
	missing = [c for c in companies if c not in have]
	if not changes and not missing:
		return

	def update(doc=doc, changes=changes, missing=missing):
		doc.update(changes)
		for company in missing:
			doc.append("accounts", account_row(company, component_type, name))
		doc.save(ignore_permissions=True)

	what = [f"{f}: {doc.get(f)!r} -> {v!r}" for f, v in changes.items()]
	if missing:
		what.append(f"accounts for {', '.join(missing)}")
	plan.do(f"Update component {name}: " + "; ".join(what), update)


def normalise(value):
	if isinstance(value, str):
		return value.strip()
	if value is None:
		return ""
	if isinstance(value, float | int):
		return flt(value)
	return value


def ensure_pay_codes(plan):
	"""Drea Finance Settings > Salary Components -> Pay Codes, so the mapping is ready when Drea HR is
	connected to Drea Finance. Drea HR itself does not need it."""
	if not frappe.db.exists("DocType", "Drea Finance Settings"):
		return
	have = dict(
		frappe.get_all(
			"Drea Finance Pay Code",
			filters={"parent": "Drea Finance Settings"},
			fields=["salary_component", "pay_code"],
			as_list=True,
		)
	)
	wanted = {name: spec[3] for name, spec in COMPONENTS.items()}
	changes = {n: c for n, c in wanted.items() if have.get(n) != c}
	retired = [n for n in RETIRED if n in have]
	if not changes and not retired:
		return

	def write():
		settings = frappe.get_single("Drea Finance Settings")
		rows = {r.salary_component: r for r in settings.pay_codes}
		for name in retired:
			settings.remove(rows.pop(name))
		for name, code in changes.items():
			if name in rows:
				rows[name].pay_code = code
			else:
				settings.append("pay_codes", {"salary_component": name, "pay_code": code})
		settings.flags.ignore_mandatory = True
		settings.save(ignore_permissions=True)

	what = [f"{n} -> {c}" for n, c in changes.items()] + [f"drop {n}" for n in retired]
	plan.do("Drea Finance pay codes: " + "; ".join(what), write)


# --- structures --------------------------------------------------------------------------------


def ensure_structure(plan, company):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = STRUCTURE_NAME.format(abbr=abbr)
	if frappe.db.exists("Salary Structure", name):
		return

	def create():
		doc = frappe.new_doc("Salary Structure")
		doc.update(
			{
				"company": company,
				"payroll_frequency": "Monthly",
				"is_active": "Yes",
				"currency": frappe.get_cached_value("Company", company, "default_currency"),
			}
		)
		for table, components in STRUCTURE.items():
			for component in components:
				_abbr, _type, formula, _code, payment_days, _taxable = COMPONENTS[component]
				doc.append(
					table,
					{
						"salary_component": component,
						"amount_based_on_formula": 1 if formula else 0,
						"formula": formula or "",
						"depends_on_payment_days": payment_days,
					},
				)
		doc.insert(ignore_permissions=True, set_name=name)  # a draft: HR checks it, then submits

	plan.do(f"Create draft salary structure {name} for {company}", create)

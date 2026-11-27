# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Drea payroll setup: salary components and their accounts, draft salary structures per company
(full-time, interns and leaders paid by prive; owner, 27 Nov 2026), Drea Finance's pay codes and
accounts, the pay calendar, and leave types that do not count holidays (handover, 5 Nov 2026
audit).

Run it as a dry run first; it prints every change and saves nothing:

    bench --site <site> execute hrms.payroll.drea_payroll_setup.apply
    bench --site <site> execute hrms.payroll.drea_payroll_setup.apply --kwargs "{'dry_run': False}"

Safe to run again: what is already right is left alone. Nothing is deleted. A component that
should go is disabled, so any old structure or slip that names it still opens.

Figures HR/Finance must confirm before production are marked CONFIRM below.
"""

import frappe
from frappe.utils import cint, flt

# --- figures -----------------------------------------------------------------------------------
# BPJS Kesehatan: 1% employee + 4% company of the wage, the wage capped at Rp12,000,000
# (Perpres 64/2020). The company pays the employee's shares too (owner, 27 Nov 2026), so each
# BPJS line below is the whole contribution: Kesehatan 5%, JHT 5.7%, JP 3%.
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
#
# Unpaid days show as their own line (owner, 27 Nov 2026: staff see why pay is lower). Basic is the
# full base, cut only for days before joining or after leaving; Unpaid Leave takes off a day's pay
# (base / working days in the period) for each day of leave without pay or absence. Same net pay
# as Frappe's own proration of Basic, but the cut is visible.
EMPLOYED_DAYS = "(payment_days + leave_without_pay + absent_days)"
UNPAID_DAYS = "(leave_without_pay + absent_days)"
COMPONENTS = {
	# earnings
	"Basic": (
		"B",
		"Earning",
		f"base * min(1, {EMPLOYED_DAYS} / total_working_days) if total_working_days else 0",
		"SALARY",
		0,
		1,
	),
	"Incentive": ("INC", "Earning", None, "INCENTIVE", 0, 1),
	# THR has its own code, so Drea Finance's transfer list can show it apart (Drea Finance, 27 Nov
	# 2026); booked with incentives on 510202. An Additional Salary in that month's payroll
	# (hrms.payroll.drea_thr).
	"THR": ("THR", "Earning", None, "THR", 0, 1),
	# A partner's drawing (prive), not salary (owner, 27 Nov 2026): every partner on this one
	# component and code; Drea Finance books it on 310200 and allocates it per partner at year end.
	# The amount is the base of their assignment on "Drea Leader". Not taxable as salary.
	"Prive": ("PRIVE", "Earning", "base", "PRIVE", 0, 0),
	# deductions taken from pay: only cuts the company keeps; they reduce salary in Finance
	"Late Penalty": ("LATE", "Deduction", "late_entry_days * 50000", "SALARY", 0, 1),  # HR's rule
	"Unpaid Leave": (
		"UnLe",
		"Deduction",
		f"min(B, base * {UNPAID_DAYS} / total_working_days) if total_working_days else 0",
		"SALARY",
		0,
		1,
	),
	# employer contributions: the company pays on top, nothing is taken from pay (owner, 27 Nov
	# 2026: the amount HR enters is what the person receives). Each BPJS line is the company's share
	# plus the employee's share the company pays for them. For PPh 21: Kesehatan, JKK and JKM paid
	# by the company count as the employee's income; JHT and JP do not. CONFIRM with the tax
	# consultant how the employee's 1% Kesehatan, 2% JHT and 1% JP paid by the company are treated.
	"BPJS Kesehatan": (
		"BPJSKES",
		"Employer Contribution",
		f"min(base, {BPJS_KES_CAP}) * 0.05",  # 4% company + 1% employee
		"BPJS_KES_COMPANY",
		0,
		1,
	),
	"BPJS JHT": ("JHT", "Employer Contribution", "base * 0.057", "BPJS_TK_COMPANY", 0, 0),  # 3.7% + 2%
	"BPJS JP": (
		"JP",
		"Employer Contribution",
		f"min(base, {JP_WAGE_CAP}) * 0.03",  # 2% company + 1% employee
		"BPJS_TK_COMPANY",
		0,
		0,
	),
	"BPJS JKM": ("JKM", "Employer Contribution", "base * 0.003", "BPJS_TK_COMPANY", 0, 1),
	"BPJS JKK": ("JKK", "Employer Contribution", f"base * {JKK_RATE}", "BPJS_TK_COMPANY", 0, 1),
	# The company pays PPh 21; it is not taken from pay (owner, 27 Nov 2026: the amount HR enters
	# is what the person receives). Worked out by hrms.payroll.drea_pph21 when Payroll Settings >
	# Calculate PPh 21 is on, so no formula here. Not grossed up: tax the company bears is not
	# the employee's income. CONFIRM with the tax consultant.
	"PPh21": ("PPh21", "Employer Contribution", None, "PPH21_COMPANY", 0, 0),
}

# Drea Finance's pay codes and the accounts in its chart they book to (Drea Finance, 27 Nov 2026):
# code: (name, kind, account, owed account). Written to Drea Finance Settings > Pay Codes -> Drea
# Finance Accounts when missing; a row HR has changed since is left as it is and reported.
# OVERPAID_RECOVERY (deduction, owed on 210201) is left out until HR takes back an overpayment.
FINANCE_CODES = {
	"SALARY": ("Gaji", "earning", "510201", None),
	"INCENTIVE": ("Insentif & Bonus", "earning", "510202", None),
	"THR": ("THR", "earning", "510202", None),
	"PRIVE": ("Prive", "earning", "310200", None),
	"BPJS_KES_COMPANY": ("BPJS Kesehatan", "employer", "510401", "210301"),
	"BPJS_TK_COMPANY": ("BPJS Ketenagakerjaan", "employer", "510402", "210302"),
	"PPH21_COMPANY": ("PPh 21 ditanggung perusahaan", "employer", "510521", "210421"),
}

# disabled, never deleted: the single 4% "BPJS" deduction (wrong rate, no split), the duplicate
# "Income Tax" (PPh21 covers it), PPh23 (a tax on payments to vendors, not on salaries), the
# second basic pay "Gaji Pokok Denalo" (Basic does it for every company), and Arrear and Leave
# Encashment (not used: no back pay runs, leave is not paid out), and the employee's BPJS
# shares as deductions (the company pays them, on its own BPJS lines; owner, 27 Nov 2026).
RETIRED = (
	"BPJS",
	"Income Tax",
	"PPh23",
	"Gaji Pokok Denalo",
	"Arrear",
	"Leave Encashment",
	"BPJS Kesehatan Karyawan",
	"BPJS JHT Karyawan",
	"BPJS JP Karyawan",
)

# The draft structures every company with employees gets (owner, 27 Nov 2026); HR checks them,
# then submits and assigns. Freelancers invoice and are not on payroll. PPh21 (paid by the
# company) is worked out by hrms.payroll.drea_pph21 when Payroll Settings > Calculate PPh 21 is on.
STRUCTURES = {
	# full-time permanent and contract staff
	"Drea Full-time - {abbr}": {
		"earnings": ["Basic"],
		"deductions": ["Unpaid Leave", "Late Penalty"],
		"employer_contributions": ["BPJS Kesehatan", "BPJS JHT", "BPJS JP", "BPJS JKM", "BPJS JKK", "PPh21"],
	},
	# interns: their allowance on Basic, no BPJS
	"Drea Intern - {abbr}": {
		"earnings": ["Basic"],
		"deductions": ["Unpaid Leave", "Late Penalty"],
		"employer_contributions": ["PPh21"],
	},
	# partners paid by drawing (prive): their monthly drawing is the base of their assignment. No
	# BPJS, PPh 21, unpaid days or late penalty: a drawing is not a salary.
	"Drea Leader - {abbr}": {
		"earnings": ["Prive"],
		"deductions": [],
		"employer_contributions": [],
	},
}
# the one draft before 27 Nov 2026, replaced by "Drea Full-time" while nobody is on it
OLD_STRUCTURE = "Drea Standard - {abbr}"

# HR Settings: a month's pay covers the 19th to the 18th (HR recaps attendance and unpaid leave on
# the 19th), paid on the 27th (owner, 27 Nov 2026; hrms.payroll.drea_pay_calendar)
PAY_CALENDAR = {"pay_period_start_day": 19, "pay_day": 27}

# leave that should not count Saturdays, Sundays and public holidays as leave days. Maternity
# and miscarriage leave stay calendar-based (the law counts them in months).
LEAVE_TYPES_WITHOUT_HOLIDAYS = (
	"Casual Leave",
	"Compensatory Off",
	"Leave Without Pay",
	"Privilege Leave",
	"Sick Leave",
)


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
			plan.do(
				f"Disable component {name}",
				lambda n=name: frappe.db.set_value("Salary Component", n, "disabled", 1),
			)
	for company in companies:
		if frappe.db.exists("Employee", {"company": company, "status": "Active"}):
			for name, tables in STRUCTURES.items():
				ensure_structure(plan, company, name, tables)
			retire_old_structure(plan, company)
	ensure_pay_calendar(plan)
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
		"prive": f"Prive - {abbr}",
	}


def root_company(company):
	"""ERPNext only lets an account be added to a group's top company, which copies it to every
	company under it (the CVs sit under "Dreambox")."""
	while parent := frappe.get_cached_value("Company", company, "parent_company"):
		company = parent
	return company


def ensure_accounts(plan, company):
	names = accounts_for(company)
	below = [c for c in frappe.get_all("Company", filters={"parent_company": company}, pluck="name")]
	copied = f" (copied to {', '.join(below)})" if below else ""
	payroll_payable = frappe.db.get_value("Account", names["payroll"], ["parent_account"], as_dict=True)
	for key, account_type in (("bpjs", "Payable"), ("pph21", "Tax")):
		if frappe.db.exists("Account", names[key]) or not payroll_payable:
			continue
		account_name = names[key].rsplit(" - ", 1)[0]

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

	# partners' drawings in Drea HR's own books (Drea Finance books them on its 310200)
	equity = frappe.db.get_value(
		"Account", {"company": company, "root_type": "Equity", "is_group": 1}, "name", order_by="lft asc"
	)
	if not frappe.db.exists("Account", names["prive"]) and equity:

		def create_prive():
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "Prive",
					"company": company,
					"parent_account": equity,
					"account_type": "Equity",
					"root_type": "Equity",
					"report_type": "Balance Sheet",
				}
			).insert(ignore_permissions=True)

		plan.do(f"Create account {names['prive']} under {equity}{copied}", create_prive)


def account_row(company, component_type, component):
	names = accounts_for(company)
	if component_type == "Earning":
		return {"company": company, "account": names["prive" if component == "Prive" else "expense"]}
	if component_type == "Deduction":
		if component.startswith("BPJS"):
			return {"company": company, "account": names["bpjs"]}
		if component == "PPh21":
			return {"company": company, "account": names["pph21"]}
		# a cut the company keeps: less salary expense
		return {"company": company, "account": names["expense"]}
	# employer contribution: company cost, owed to BPJS or (PPh 21) the tax office
	owed = names["pph21"] if component == "PPh21" else names["bpjs"]
	return {"company": company, "account": names["expense"], "liability_account": owed}


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

		plan.do(
			f"Create component {name} ({component_type}, {code}, {formula or 'amount per month'})", create
		)
		return

	doc = frappe.get_doc("Salary Component", name)
	changes = {f: v for f, v in wanted.items() if normalise(doc.get(f)) != normalise(v)}
	have = {row.company for row in doc.accounts}
	missing = [c for c in companies if c not in have]

	# rows whose accounts no longer fit (PPh21 became a company cost on 27 Nov 2026)
	def fits(row):
		want = account_row(row.company, component_type, name)
		return (row.account, row.get("liability_account") or None) == (
			want["account"],
			want.get("liability_account"),
		)

	wrong = [row for row in doc.accounts if row.company in companies and not fits(row)]
	if not changes and not missing and not wrong:
		return

	def update(doc=doc, changes=changes, missing=missing, wrong=wrong):
		doc.update(changes)
		for row in wrong:
			row.update(account_row(row.company, component_type, name))
		for company in missing:
			doc.append("accounts", account_row(company, component_type, name))
		doc.save(ignore_permissions=True)

	what = [f"{f}: {doc.get(f)!r} -> {v!r}" for f, v in changes.items()]
	if missing:
		what.append(f"accounts for {', '.join(missing)}")
	if wrong:
		what.append(f"accounts corrected for {', '.join(r.company for r in wrong)}")
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
	"""Drea Finance Settings: the pay codes with their Drea Finance accounts, and Salary Component ->
	pay code, so both are ready when Drea HR is connected to Drea Finance. Drea HR itself does not
	need them. One save, so the settings' checks see both tables at once."""
	if not frappe.db.exists("DocType", "Drea Finance Settings"):
		return
	settings = frappe.get_single("Drea Finance Settings")
	have_codes = {r.pay_code: r for r in settings.get("codes", [])}
	new_codes = [code for code in FINANCE_CODES if code not in have_codes]
	for code, (_name, kind, account, owed) in FINANCE_CODES.items():
		row = have_codes.get(code)
		if row and (row.kind, row.account or None, row.owed_account or None) != (kind, account, owed):
			print(
				f"   pay code {code} differs from Drea Finance's list ({row.kind} {row.account or '-'} "
				f"{row.owed_account or '-'}, list: {kind} {account or '-'} {owed or '-'}): left as it is"
			)
	known = set(have_codes) | set(FINANCE_CODES)

	have = {r.salary_component: r.pay_code for r in settings.pay_codes}
	wanted = {name: spec[3] for name, spec in COMPONENTS.items()}
	changes = {n: c for n, c in wanted.items() if have.get(n) != c}
	# retired components, and codes Drea Finance no longer has (the per-partner PRIVE_<NAME>)
	dropped = [n for n, c in have.items() if n in RETIRED or c not in known]
	if not new_codes and not changes and not dropped:
		return

	def write():
		settings = frappe.get_single("Drea Finance Settings")
		for code in new_codes:
			name, kind, account, owed = FINANCE_CODES[code]
			settings.append(
				"codes",
				{"pay_code": code, "code_name": name, "kind": kind, "account": account, "owed_account": owed},
			)
		rows = {r.salary_component: r for r in settings.pay_codes}
		for name in dropped:
			settings.remove(rows.pop(name))
		for name, code in changes.items():
			if name in rows:
				rows[name].pay_code = code
			else:
				settings.append("pay_codes", {"salary_component": name, "pay_code": code})
		settings.flags.ignore_mandatory = True
		settings.save(ignore_permissions=True)

	what = (
		[
			f"add {c} ({FINANCE_CODES[c][1]}, {FINANCE_CODES[c][2] or '-'} / {FINANCE_CODES[c][3] or '-'})"
			for c in new_codes
		]
		+ [f"{n} -> {c}" for n, c in changes.items()]
		+ [f"drop {n} ({have[n]})" for n in dropped]
	)
	plan.do("Drea Finance pay codes: " + "; ".join(what), write)


# --- structures --------------------------------------------------------------------------------


def structure_rows(tables):
	rows = []
	for table, components in tables.items():
		for component in components:
			_abbr, _type, formula, _code, payment_days, _taxable = COMPONENTS[component]
			rows.append(
				{
					"parentfield": table,
					"salary_component": component,
					"amount_based_on_formula": 1 if formula else 0,
					"formula": formula or "",
					"depends_on_payment_days": payment_days,
				}
			)
	return rows


def ensure_structure(plan, company, name, tables):
	"""A draft structure is brought up to date; a submitted one is HR's and only reported."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = name.format(abbr=abbr)
	wanted = structure_rows(tables)

	if frappe.db.exists("Salary Structure", name):
		doc = frappe.get_doc("Salary Structure", name)
		have = [
			{
				"parentfield": row.parentfield,
				"salary_component": row.salary_component,
				"amount_based_on_formula": row.amount_based_on_formula,
				"formula": (row.formula or "").strip(),
				"depends_on_payment_days": row.depends_on_payment_days,
			}
			for table in tables
			for row in doc.get(table)
		]
		if have == wanted:
			return
		if doc.docstatus != 0:
			print(f"   {name} is submitted and differs from the standard: HR to cancel and amend it")
			return

		def rebuild(doc=doc):
			for table in tables:
				doc.set(table, [])
			for row in wanted:
				doc.append(row["parentfield"], {k: v for k, v in row.items() if k != "parentfield"})
			doc.save(ignore_permissions=True)

		plan.do(f"Update draft salary structure {name}", rebuild)
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
		for row in wanted:
			doc.append(row["parentfield"], {k: v for k, v in row.items() if k != "parentfield"})
		doc.insert(ignore_permissions=True, set_name=name)  # a draft: HR checks it, then submits

	plan.do(f"Create draft salary structure {name} for {company}", create)


def retire_old_structure(plan, company):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = OLD_STRUCTURE.format(abbr=abbr)
	if not frappe.db.exists("Salary Structure", {"name": name, "docstatus": 0}):
		return
	if frappe.db.exists("Salary Structure Assignment", {"salary_structure": name}):
		print(f"   kept {name}: it is assigned")
		return
	plan.do(
		f"Delete draft salary structure {name} (replaced by Drea Full-time)",
		lambda: frappe.delete_doc("Salary Structure", name, ignore_permissions=True),
	)


# --- pay calendar ------------------------------------------------------------------------------


def ensure_pay_calendar(plan):
	meta = frappe.get_meta("HR Settings")
	changes = {
		field: value
		for field, value in PAY_CALENDAR.items()
		if meta.has_field(field) and cint(frappe.db.get_single_value("HR Settings", field)) != value
	}
	if changes:
		plan.do(
			"HR Settings: " + "; ".join(f"{f} -> {v}" for f, v in changes.items()),
			lambda: [frappe.db.set_single_value("HR Settings", f, v) for f, v in changes.items()],
		)


# --- leaders paid by drawing (prive) -----------------------------------------------------------
# A leader who is a partner of their CV takes their pay as a drawing (prive), not salary (owner,
# 27 Nov 2026). Every partner is on "Drea Leader - <abbr>" (STRUCTURES), with their own monthly
# drawing as the base of their assignment (hrms.payroll.drea_pay_sheet). One component and one
# pay code, PRIVE, for all of them: Drea Finance books it on 310200 and refuses it in a company
# with no partner on the pay date.
LEADER_STRUCTURE = "Drea Leader - {abbr}"

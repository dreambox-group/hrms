# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Drea organisation setup (owner, 25 Nov 2026): four legal entities with no parent company, the
departments in the CV that employs their people, the job titles and employment types in use, no
employee grades, and the fixes to a few employee records.

Dry run first; it prints every change and saves nothing:

    bench --site <site> execute hrms.hr.drea_org_setup.apply
    bench --site <site> execute hrms.hr.drea_org_setup.apply --kwargs "{'dry_run': False}"

Safe to run again: what is already right is left alone.
"""

import frappe
from frappe.utils.nestedset import get_root_of, rebuild_tree

DENALO = "CV Dreambox Denalo International"
KOTAK_MIMPI = "CV Kotak Mimpi Creative"
OLD_PARENT = "Dreambox"  # the group company the dev team made; Dreambox has no parent company

# department name: (company, parent department name or None for the top, is a group, old name)
DEPARTMENTS = {
	"Holding": (DENALO, None, 1, "Holding - Db"),
	"Director": (DENALO, "Holding", 0, "Director - Db"),
	"Finance": (DENALO, "Holding", 0, "Finance - Db"),
	"HR": (DENALO, "Holding", 0, "HR - Db"),
	"Account": (DENALO, "Holding", 0, "Marketing  - Db"),  # was Marketing (its people are "Account")
	"Creashun": (DENALO, None, 0, "Creashun - Db"),
	"Digital": (DENALO, None, 0, "Digital - Db"),
	"Mind Sequence": (DENALO, None, 0, "Mind Sequence - Db"),
	"Reagentive": (DENALO, None, 0, "Reagentive - Db"),
	"Shoot by Code": (DENALO, None, 0, "Shoot by Code - Db"),
	"Littlebit": (KOTAK_MIMPI, None, 0, "Littlebit - Db"),
}
# Payroll Test was a test; Creator Led is Creashun's old name (same Drea Finance division)
DELETED_DEPARTMENTS = ("Payroll Test - Db", "Creator Led - Db", "Creator Led - DIGITAL DENALO")

# what the old parent company still held: moved to Denalo, or test and sample records deleted
MOVED_TO_DENALO = ("Email Account",)  # "Drea HR", the outgoing mail account
DELETED_WITH_OLD_PARENT = (  # order matters: what links to the next comes first
	"Appointment Letter",
	"Job Offer",
	"Job Opening",
	"Employee Onboarding Template",
	"Employee Separation Template",
	"Training Program",
	"Leave Block List",
)

EMPLOYMENT_TYPES = ("Full-time Permanent", "Full-time Contract", "Intern", "Freelance")
EMPLOYMENT_TYPE_RENAMES = {"Full-time": "Full-time Permanent", "Contract": "Full-time Contract"}
WITHOUT_LEAVE_ALLOCATION = ("Intern", "Freelance")  # no leave quota (HR Settings)

NEW_DESIGNATIONS = ("IT Developer",)

TEST_EMPLOYEES = ("TESTFINANCE",)
# employee: fields to set (Aaron and Obie)
EMPLOYEE_FIXES = {
	"HR-EMP-00056": {"employment_type": "Freelance", "designation": "IT Developer", "branch": "Tangerang"},
	"HR-EMP-00055": {"employment_type": "Freelance", "designation": "IT Developer", "branch": "Tangerang"},
}
# main department (payroll, approvals); they also work in Mind Sequence (Employee > Secondary Departments)
EMPLOYEE_DEPARTMENTS = {"HR-EMP-00056": "Reagentive", "HR-EMP-00055": "Reagentive"}
EMPLOYEE_ALSO_WORKS_IN = {"HR-EMP-00056": ["Mind Sequence"], "HR-EMP-00055": ["Mind Sequence"]}


class Plan:
	def __init__(self, dry_run):
		self.dry_run = dry_run
		self.lines = []

	def do(self, message, action):
		self.lines.append(message)
		if not self.dry_run:
			action()


def apply(dry_run=True, employee_departments=None):
	"""employee_departments: {employee: department name}, e.g. {"HR-EMP-00056": "Mind Sequence"}."""
	dry_run = dry_run not in (False, 0, "0", "false", "False")
	plan = Plan(dry_run)

	detach_companies(plan)
	attach_parent_settings(plan, (DENALO, KOTAK_MIMPI))
	clear_old_parent(plan)
	arrange_departments(plan)
	tidy_employment_types(plan)
	tidy_designations(plan)
	remove_grades(plan)
	fix_employees(plan, employee_departments or EMPLOYEE_DEPARTMENTS)
	remove_old_parent(plan)  # last: everything above has moved off it

	if not dry_run:
		frappe.db.commit()  # nosemgrep: a bench execute command, run by hand
	print(f"{'DRY RUN, nothing saved' if dry_run else 'APPLIED'}: {len(plan.lines)} change(s)")
	for line in plan.lines:
		print(" -", line)
	return plan.lines


# --- companies ---------------------------------------------------------------------------------


def detach_companies(plan):
	children = frappe.get_all("Company", filters={"parent_company": OLD_PARENT}, pluck="name", order_by="name")
	if not children:
		return

	def detach():
		for company in children:
			frappe.db.set_value("Company", company, "parent_company", None)
		rebuild_tree("Company")
		frappe.clear_cache(doctype="Company")

	plan.do(f"Detach {', '.join(children)} from {OLD_PARENT} (no parent company)", detach)


def attach_parent_settings(plan, companies):
	"""What HR set on the parent never reached the CVs; give them the same."""
	for assignment in frappe.get_all(
		"Holiday List Assignment",
		filters={"applicable_for": "Company", "assigned_to": OLD_PARENT, "docstatus": 1},
		fields=["holiday_list", "from_date"],
	):
		for company in companies:
			if frappe.db.exists(
				"Holiday List Assignment",
				{"applicable_for": "Company", "assigned_to": company, "docstatus": 1, "from_date": ("<=", assignment.from_date)},
			):
				continue

			def assign(company=company, a=assignment):
				doc = frappe.get_doc(
					{
						"doctype": "Holiday List Assignment",
						"applicable_for": "Company",
						"assigned_to": company,
						"holiday_list": a.holiday_list,
						"from_date": a.from_date,
					}
				)
				doc.insert(ignore_permissions=True)
				doc.submit()

			plan.do(f"Holiday list {assignment.holiday_list} for {company} from {assignment.from_date}", assign)

	for period in frappe.get_all(
		"Leave Period", filters={"company": OLD_PARENT, "is_active": 1}, fields=["from_date", "to_date", "optional_holiday_list"]
	):
		for company in companies:
			if frappe.db.exists(
				"Leave Period", {"company": company, "from_date": period.from_date, "to_date": period.to_date}
			):
				continue

			def add(company=company, p=period):
				frappe.get_doc(
					{
						"doctype": "Leave Period",
						"company": company,
						"from_date": p.from_date,
						"to_date": p.to_date,
						"is_active": 1,
						"optional_holiday_list": p.optional_holiday_list,
					}
				).insert(ignore_permissions=True)

			plan.do(f"Leave period {period.from_date} to {period.to_date} for {company}", add)


def clear_old_parent(plan):
	"""Move what the old parent company still holds that HR uses, delete its test and sample records."""
	if not frappe.db.exists("Company", OLD_PARENT):
		return
	for doctype in MOVED_TO_DENALO:
		for name in frappe.get_all(doctype, filters={"company": OLD_PARENT}, pluck="name"):
			plan.do(
				f"{doctype} {name!r}: company {OLD_PARENT} -> {DENALO}",
				lambda d=doctype, n=name: frappe.db.set_value(d, n, "company", DENALO),
			)
	for doctype in DELETED_WITH_OLD_PARENT:
		for name in frappe.get_all(doctype, filters={"company": OLD_PARENT}, pluck="name"):
			plan.do(f"Delete {doctype} {name!r} ({OLD_PARENT})", lambda d=doctype, n=name: delete_record(d, n))


def remove_old_parent(plan):
	"""Delete the old parent company and what only it held: test projects and tasks, demo salary
	structures, test journal entries (their payroll runs are long gone, so they can't be cancelled
	the normal way: their ledger rows are removed directly, as ERPNext's Delete Company Transactions
	would), its holiday assignment, leave period and per-company account rows. Then ERPNext's own
	company delete removes its accounts, cost centers and warehouses."""
	C = OLD_PARENT
	if not frappe.db.exists("Company", C):
		return
	if frappe.db.exists("Employee", {"company": C}):
		print(f"   kept company {C!r}: employees still belong to it")
		return

	def remove():
		journals = frappe.get_all("Journal Entry", filters={"company": C}, pluck="name")
		if journals:
			frappe.db.delete("Journal Entry Account", {"parent": ("in", journals)})
			frappe.db.delete("Journal Entry", {"name": ("in", journals)})
		for doctype in ("GL Entry", "Payment Ledger Entry"):
			frappe.db.delete(doctype, {"company": C})
		for doctype in ("Task", "Project"):
			for name in frappe.get_all(doctype, filters={"company": C}, pluck="name"):
				frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
		for doctype, field in (("Salary Structure", "company"), ("Holiday List Assignment", "assigned_to")):
			for name in frappe.get_all(doctype, filters={field: C}, pluck="name"):
				doc = frappe.get_doc(doctype, name)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc(doctype, name, ignore_permissions=True)
		for name in frappe.get_all("Leave Period", filters={"company": C}, pluck="name"):
			frappe.delete_doc("Leave Period", name, ignore_permissions=True)
		for child in ("Salary Component Account", "Expense Claim Account", "Mode of Payment Account"):
			frappe.db.delete(child, {"company": C})
		# "chart of accounts copied from" on the CVs, and the earlier AppSheet import runs
		frappe.db.sql('update "tabCompany" set existing_company = null where existing_company = %s', C)
		if frappe.db.has_column("Old HRIS Import", "default_company"):
			frappe.db.sql(
				'update "tabOld HRIS Import" set default_company = %s where default_company = %s', (DENALO, C)
			)
		if frappe.db.table_exists("Old HRIS Import Mapping"):  # the runs' "Business -> Company" rows
			frappe.db.sql(
				"""update "tabOld HRIS Import Mapping" set maps_to = %s
				where link_doctype = 'Company' and maps_to = %s""",
				(DENALO, C),
			)
		frappe.delete_doc("Company", C, ignore_permissions=True)

	counts = {
		"projects": frappe.db.count("Project", {"company": C}),
		"tasks": frappe.db.count("Task", {"company": C}),
		"salary structures": frappe.db.count("Salary Structure", {"company": C}),
		"test journal entries": frappe.db.count("Journal Entry", {"company": C}),
	}
	plan.do(
		f"Delete company {C!r} with its " + ", ".join(f"{n} {k}" for k, n in counts.items() if n),
		remove,
	)


def delete_record(doctype, name):
	"""Cancel first if submitted; a record something else still links to is kept and reported."""
	frappe.db.savepoint("org_setup_record")
	try:
		doc = frappe.get_doc(doctype, name)
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc(doctype, name, ignore_permissions=True)
	except (frappe.LinkExistsError, frappe.ValidationError) as e:
		frappe.db.rollback(save_point="org_setup_record")  # undo a half-done cancel
		print(f"   kept {doctype} {name!r}: {frappe.utils.strip_html(str(e))[:160]}")


# --- departments -------------------------------------------------------------------------------


def full_name(department_name, company):
	return f"{department_name} - {frappe.get_cached_value('Company', company, 'abbr')}"


def arrange_departments(plan):
	root = get_root_of("Department")
	for department_name, (company, parent, is_group, old) in DEPARTMENTS.items():
		target = full_name(department_name, company)
		parent_name = full_name(parent, DEPARTMENTS[parent][0]) if parent else root

		if not frappe.db.exists("Department", target):
			if frappe.db.exists("Department", old):

				def move(old=old, target=target, company=company, department_name=department_name):
					frappe.db.set_value("Department", old, {"company": company, "department_name": department_name})
					frappe.clear_document_cache("Department", old)
					frappe.rename_doc("Department", old, target, force=True, show_alert=False)

				plan.do(f"Department {old!r} -> {target!r} ({company})", move)
			else:

				def create(department_name=department_name, company=company, is_group=is_group):
					frappe.get_doc(
						{"doctype": "Department", "department_name": department_name, "company": company, "is_group": is_group}
					).insert(ignore_permissions=True)

				plan.do(f"Create department {target!r} ({company})", create)

		current = frappe.db.get_value("Department", target, ["parent_department", "is_group"], as_dict=True) or {}
		if current.get("parent_department") != parent_name or (current and current.is_group != is_group):

			def place(target=target, parent_name=parent_name, is_group=is_group):
				doc = frappe.get_doc("Department", target)
				doc.parent_department = parent_name
				doc.is_group = is_group
				doc.save(ignore_permissions=True)

			plan.do(f"Department {target!r} under {parent_name!r}", place)

	for name in DELETED_DEPARTMENTS:
		if frappe.db.exists("Department", name):
			plan.do(f"Delete department {name!r}", lambda n=name: frappe.delete_doc("Department", n, ignore_permissions=True))


# --- employment types, job titles, grades --------------------------------------------------------


def tidy_employment_types(plan):
	for old, new in EMPLOYMENT_TYPE_RENAMES.items():
		if frappe.db.exists("Employment Type", old) and not frappe.db.exists("Employment Type", new):
			plan.do(
				f"Employment type {old!r} -> {new!r} (its employees follow)",
				lambda o=old, n=new: frappe.rename_doc("Employment Type", o, n, force=True, show_alert=False),
			)
	for name in EMPLOYMENT_TYPES:
		if not frappe.db.exists("Employment Type", name) and name not in EMPLOYMENT_TYPE_RENAMES.values():
			plan.do(
				f"Create employment type {name!r}",
				lambda n=name: frappe.get_doc({"doctype": "Employment Type", "employee_type_name": n}).insert(
					ignore_permissions=True
				),
			)
	keep = set(EMPLOYMENT_TYPES) | set(EMPLOYMENT_TYPE_RENAMES)
	for name in frappe.get_all("Employment Type", pluck="name"):
		if name not in keep:
			delete_if_unused(plan, "Employment Type", name, "employment_type")

	listed = set(
		frappe.get_all(
			"HR Settings Employment Type",
			filters={"parent": "HR Settings", "parentfield": "employment_types_without_leave_allocation"},
			pluck="employment_type",
		)
	)
	missing = [t for t in WITHOUT_LEAVE_ALLOCATION if t not in listed]
	if missing:

		def add():
			settings = frappe.get_single("HR Settings")
			for name in missing:
				settings.append("employment_types_without_leave_allocation", {"employment_type": name})
			settings.save(ignore_permissions=True)

		plan.do(f"No leave quota for {', '.join(missing)} (HR Settings)", add)


def tidy_designations(plan):
	for name in NEW_DESIGNATIONS:
		if not frappe.db.exists("Designation", name):
			plan.do(
				f"Create job title {name!r}",
				lambda n=name: frappe.get_doc({"doctype": "Designation", "designation_name": n}).insert(
					ignore_permissions=True
				),
			)
	wanted = set(NEW_DESIGNATIONS) | {f["designation"] for f in EMPLOYEE_FIXES.values() if f.get("designation")}
	for name in frappe.get_all("Designation", pluck="name", order_by="name"):
		if name not in wanted:
			delete_if_unused(plan, "Designation", name, "designation", quiet=True)


def remove_grades(plan):
	for employee in frappe.get_all("Employee", filters={"grade": ("is", "set")}, pluck="name"):
		plan.do(f"Employee {employee}: no grade", lambda e=employee: frappe.db.set_value("Employee", e, "grade", None))
	for name in frappe.get_all("Employee Grade", pluck="name"):
		plan.do(f"Delete grade {name!r}", lambda n=name: frappe.delete_doc("Employee Grade", n, ignore_permissions=True))


def delete_if_unused(plan, doctype, name, employee_field, quiet=False):
	if frappe.db.exists("Employee", {employee_field: name}):
		return  # in use by someone (any status): kept
	plan.do(f"Delete {doctype.lower()} {name!r} (unused)", lambda: try_delete(doctype, name))


def try_delete(doctype, name):
	try:
		frappe.delete_doc(doctype, name, ignore_permissions=True)
	except frappe.LinkExistsError:
		print(f"   kept {doctype} {name!r}: other records link to it")


# --- employees ---------------------------------------------------------------------------------


def fix_employees(plan, employee_departments):
	for employee in TEST_EMPLOYEES:
		if not frappe.db.exists("Employee", employee):
			continue
		user = frappe.db.get_value("Employee", employee, "user_id")

		def remove(employee=employee):
			# the login stays as it is: it may be a real person's (the test record used a developer's)
			frappe.db.set_value("Employee", employee, "user_id", None)
			frappe.delete_doc("Employee", employee, ignore_permissions=True, force=True)

		plan.do(f"Delete test employee {employee}" + (f" (its login {user} is kept)" if user else ""), remove)

	for employee, fields in EMPLOYEE_FIXES.items():
		if not frappe.db.exists("Employee", employee):
			continue
		wanted = dict(fields)
		if employee in employee_departments:
			name = employee_departments[employee]
			wanted["department"] = full_name(name, DEPARTMENTS[name][0])
		current = frappe.db.get_value("Employee", employee, list(wanted), as_dict=True)
		changes = {f: v for f, v in wanted.items() if current.get(f) != v}
		if changes:
			plan.do(
				f"Employee {employee}: " + ", ".join(f"{f} {current.get(f)!r} -> {v!r}" for f, v in changes.items()),
				lambda e=employee, c=changes: frappe.db.set_value("Employee", e, c),
			)

	if not frappe.db.table_exists("Employee Additional Department"):
		return  # run bench migrate first: it adds Employee > Secondary Departments
	for employee, names in EMPLOYEE_ALSO_WORKS_IN.items():
		if not frappe.db.exists("Employee", employee):
			continue
		wanted = [full_name(n, DEPARTMENTS[n][0]) for n in names]
		have = frappe.get_all(
			"Employee Additional Department", filters={"parent": employee, "parenttype": "Employee"}, pluck="department"
		)
		missing = [d for d in wanted if d not in have]
		if missing:

			def add(employee=employee, missing=missing):
				doc = frappe.get_doc("Employee", employee)
				for department in missing:
					doc.append("additional_departments", {"department": department})
				doc.flags.ignore_mandatory = True
				doc.save(ignore_permissions=True)

			plan.do(f"Employee {employee}: secondary department {', '.join(missing)}", add)

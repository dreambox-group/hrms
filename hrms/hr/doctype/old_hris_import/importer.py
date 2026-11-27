# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Old HRIS (AppSheet) -> Frappe HR, one step per old sheet. Every step is safe to run again.

Employees are matched to existing ones by their old Employee ID (kept in Employee Number), then by
email, then by exact full name; a matched employee only gets the fields that are still empty. Leave,
allocations and attendance keep their old ID in "Old HRIS ID", which is how a rerun skips them.

Historical leave and attendance skip Frappe's day-to-day checks (backdating, balances, approvers,
selfies), because the old system already decided them; instead every record is checked here
against what is already in Frappe (overlapping leave, attendance on that day) and anything doubtful
is reported, not guessed.
"""

import re
from collections import Counter, defaultdict
from datetime import date

import frappe
from frappe.utils import add_days, getdate, strip_html, today

from hrms.hr.doctype.leave_application.leave_end_date import uses_leave_end_date
from hrms.hr.doctype.old_hris_import.source import (
	Workbook,
	digits,
	email,
	key,
	text,
	to_date,
	to_datetime,
	to_latlong,
	to_number,
)

EMPLOYEES = "A.01. Employee Database"
TEAMS = "A.02. Team Database"
ATTENDANCE = "B.01. Attendance"
BALANCES = "C.01. Leave Balance"
LEAVE_LOG = "C.02. Leave Log"
ATTENDANCE_HEADERS = ("Employee ID", "Date", "Status")

# old column -> what HR matches it to (Old HRIS Import Mapping)
MAPPED_COLUMNS = {"Business": "Company", "Team": "Department", "Type": "Employment Type", "Placement": "Branch"}
EMPLOYMENT_TYPE_GUESSES = {  # Dreambox's four employment types
	"fulltimepermanent": "Full-time Permanent",
	"fulltime": "Full-time Permanent",
	"permanent": "Full-time Permanent",
	"fulltimecontract": "Full-time Contract",
	"contract": "Full-time Contract",
	"intern": "Intern",
	"internship": "Intern",
	"magang": "Intern",
	"freelance": "Freelance",
	"freelancer": "Freelance",
}
PERMANENT = "Full-time Permanent"  # the one type without a contract end date
# the employee tab as HR keeps it now -> the old AppSheet titles the importer reads (used when the old one is missing)
EMPLOYEE_TITLES = {
	"Employee Number": "Employee ID",
	"Status": "Type",
	"Designation": "Position",
	"Division": "Team",
	"Legal Entity": "Business",
	"Promoted": "Promoted Date",
	"NIK": "Personal ID",
	"Supervisor 1": "Supervisor 1 ID",
	"Supervisor 2": "Supervisor 2 ID",
}
# Status Kawin -> Employee's marital status; the first word found wins ("belum kawin" before "kawin")
MARITAL_WORDS = (
	("belum", "Single"), ("lajang", "Single"), ("single", "Single"), ("tk", "Single"),
	("cerai", "Divorced"), ("divorce", "Divorced"),
	("janda", "Widowed"), ("duda", "Widowed"), ("widow", "Widowed"),
	("menikah", "Married"), ("kawin", "Married"), ("married", "Married"), ("k", "Married"),
)
# Old HRIS Role -> roles on a new login; supervisors get Leave Approver from their team
LOGIN_ROLES = {"admin": ["HR Manager"], "hrteam": ["HR User"]}
BASE_ROLES = ["Employee", "Employee Self Service"]
HR_ROLES = {"System Manager", "HR Manager", "HR User"}
FREE_MAIL = ("gmail.", "yahoo.", "hotmail.", "outlook.", "icloud.", "live.", "ymail.", "rocketmail.")
# words in an old "Special" leave reason -> words in the leave type's name; most specific first
SPECIAL_LEAVE_WORDS = (
	("keguguran", "keguguran"),
	("miscarriage", "keguguran"),
	("istri melahirkan", "istri melahirkan"),
	("istri lahiran", "istri melahirkan"),
	("melahirkan", "melahirkan"),
	("lahiran", "melahirkan"),
	("menikah", "menikah"),
	("nikah", "menikah"),
	("wedding", "menikah"),
	("duka", "duka"),
	("meninggal", "duka"),
	("wafat", "duka"),
	("sakit", "sakit"),
	("sick", "sakit"),
)
ATTENDANCE_STATUS = {"present": ("Present", 0), "late": ("Present", 1), "absent": ("Absent", 0)}
ATTENDANCE_SKIPPED = ("onleave", "nonworkingday")
STATUS_WORDS = ("Present", "Late", "Absent", "On Leave", "Non Working Day")
MAX_MESSAGES = 3000


class Report:
	def __init__(self):
		self.counts = Counter()
		self.messages = []
		self.dropped = 0

	def count(self, what, n=1):
		self.counts[what] += n

	def add(self, level, sheet, row, message):
		"""level: 'error' = the row was not imported, 'warning' = imported with a change, 'info'."""
		if len(self.messages) >= MAX_MESSAGES:
			self.dropped += 1
			return
		row = row.get("_row") if isinstance(row, dict) else row
		self.messages.append([level, sheet, row or "", message])

	def as_dict(self):
		levels = Counter(m[0] for m in self.messages)
		return {
			"counts": dict(sorted(self.counts.items())),
			"messages": self.messages,
			"errors": levels["error"],
			"warnings": levels["warning"],
			"dropped": self.dropped,
		}


class OldHRISImporter:
	def __init__(self, doc, dry_run=True):
		self.doc = doc
		self.dry_run = dry_run
		self.report = Report()
		self.book = Workbook(file_path(doc.workbook))
		self.archives = [(row.file, Workbook(file_path(row.file))) for row in doc.attendance_files]
		self.import_from = getdate(doc.import_from) if doc.import_from else None
		self.mapping = {(row.column, key(row.old_value)): row.maps_to for row in doc.mappings}
		self.employees = {}  # old Employee ID -> Employee name
		self.departments = {}  # (old team, company) -> Department
		self.by_number = None  # Employee Number -> Employee, for IDs not in the employee tab
		self.employment = {}  # Employee -> (joining date, relieving date)

	# ------------------------------------------------------------ matching table

	def people(self):
		"""The employee tab, with today's titles ("Employee Number", "Division"...) read as the old ones."""
		rows = self.book.rows(EMPLOYEES)
		for row in rows:
			for title, old in EMPLOYEE_TITLES.items():
				if title in row and old not in row:
					row[old] = row.pop(title)
		return rows

	def refresh_mappings(self):
		"""Adds a row for every old value not in the table yet, with a guess; HR's choices stay."""
		people = self.people()
		# one row per value as the importer compares them: "People" and "people " are one team
		values, spelling = defaultdict(Counter), defaultdict(dict)
		for row in self.book.rows(TEAMS) if people else []:  # A.02 spells a team's name first
			if text(row.get("Team Name")):
				values["Team"].setdefault(key(row.get("Team Name")), 0)
				spelling["Team"].setdefault(key(row.get("Team Name")), text(row.get("Team Name")))
		for row in people:
			for column in MAPPED_COLUMNS:
				if text(row.get(column)):
					values[column][key(row.get(column))] += 1
					spelling[column].setdefault(key(row.get(column)), text(row.get(column)))

		# a table from before values were compared this way can hold one value twice; keep HR's choice
		existing = {}
		for row in sorted(self.doc.mappings, key=lambda r: (not r.maps_to, r.idx)):
			if (row.column, key(row.old_value)) in existing:
				self.doc.remove(row)
			else:
				existing[(row.column, key(row.old_value))] = row
		for column, link_doctype in MAPPED_COLUMNS.items():
			for k, count in sorted(values[column].items(), key=lambda v, c=column: spelling[c][v[0]].lower()):
				old_value = spelling[column][k]
				row = existing.get((column, k))
				if row:
					row.rows = count
					if not row.maps_to and link_doctype == "Department":
						# a team left empty becomes the company's department of that name anyway: show which
						row.maps_to = guess(link_doctype, old_value, self.doc.default_company)
					continue
				self.doc.append(
					"mappings",
					{
						"column": column,
						"old_value": old_value,
						"rows": count,
						"link_doctype": link_doctype,
						"maps_to": guess(link_doctype, old_value, self.doc.default_company),
					},
				)
		self.mapping = {(row.column, key(row.old_value)): row.maps_to for row in self.doc.mappings}

	def mapped(self, column, value):
		return self.mapping.get((column, key(value))) if text(value) else None

	# ------------------------------------------------------------ the steps

	def run(self):
		people = self.people()
		steps = []
		if people:
			steps = [
				("departments", lambda: self.prepare_departments(people, self.book.rows(TEAMS))),
				("employees", lambda: self.import_employees(people)),
				("supervisors", lambda: self.link_supervisors(people)),
			]
			if self.doc.create_logins:
				steps.append(("logins", lambda: self.create_logins(people)))
			steps.append(("leave approvers", lambda: self.set_leave_approvers(self.book.rows(TEAMS))))
		else:
			self.report.add(
				"info",
				EMPLOYEES,
				"",
				"No employee rows: leave and attendance go to the people already in Drea HR, by Employee Number. "
				"The team tab is not used.",
			)
		steps += [
			("leave balances", lambda: self.import_balances(self.book.rows(BALANCES))),
			("leave", lambda: self.import_leave(self.book.rows(LEAVE_LOG))),
			("attendance", lambda: self.import_attendance(ATTENDANCE, self.book.rows(ATTENDANCE))),
		]
		for label, workbook in self.archives:
			for sheet, rows in workbook.all_rows(ATTENDANCE_HEADERS):
				steps.append(("attendance", lambda s=f"{file_name(label)} / {sheet}", r=rows: self.import_attendance(s, r)))

		for _label, step in steps:
			step()
			self.commit()
		return self.report.as_dict()

	def commit(self):
		if not self.dry_run:
			frappe.db.commit()

	def each(self, sheet, rows, handle):
		"""Runs `handle(row)` per row; a row that fails is rolled back alone and reported."""
		for n, row in enumerate(rows, start=1):
			frappe.db.savepoint("old_hris_row")
			try:
				handle(row)
			except Exception as e:
				frappe.db.rollback(save_point="old_hris_row")
				self.report.add("error", sheet, row, f"Not imported: {error_text(e)}")
			finally:
				frappe.local.message_log = []
			if n % 200 == 0:
				self.commit()

	# ------------------------------------------------------------ employees

	def import_employees(self, rows):
		seen = set()
		existing = existing_employees()
		missing_personal = 0
		for row in rows:
			old_id = text(row.get("Employee ID"))
			if not old_id:
				self.report.add("error", EMPLOYEES, row, "No Employee ID.")
				continue
			if old_id in seen:
				self.report.add("error", EMPLOYEES, row, f"Employee ID {old_id} appears twice; only the first row is used.")
				continue
			seen.add(old_id)
			match, how = existing.find(old_id, email(row.get("Email")), text(row.get("Name")))
			if match == "ambiguous":
				self.report.add(
					"error", EMPLOYEES, row, f"{old_id} {text(row.get('Name'))}: {how}; fix it in Frappe first."
				)
				continue
			if match:
				self.employees[old_id] = match
				self.each(EMPLOYEES, [row], lambda r: self.fill_employee(match, r, how))
				continue

			def create(r, old_id=old_id):
				self.employees[old_id] = self.create_employee(r)

			self.each(EMPLOYEES, [row], create)
			missing_personal += old_id in self.employees
		meta = frappe.get_meta("Employee")
		required = [meta.get_label(f) for f in ("gender", "date_of_birth") if meta.get_field(f) and meta.get_field(f).reqd]
		if missing_personal and required:  # a site can make them optional (Customize Form)
			self.report.add(
				"info",
				EMPLOYEES,
				"",
				f"{missing_personal} new employees have no {' or '.join(required).lower()} (the old HRIS didn't keep them). "
				"Frappe asks for it the next time someone edits the employee.",
			)

	def employee_values(self, row):
		old_id = text(row.get("Employee ID"))
		employment_type = self.mapped("Type", row.get("Type"))
		mail = email(row.get("Email"))
		personal_mail = bool(mail) and any(f"@{p}" in mail for p in FREE_MAIL)
		account = text(row.get("Account Number"))
		joined = to_date(row.get("Join Date")) or to_date(row.get("Timestamp"))
		end = to_date(row.get("End Date"))
		# today's sheet has no such column and lists only the people working now: its End Date is when
		# a contract (or, for permanent staff, the first contract or probation) ends, not when they left
		active = key(row.get("Employment Status")) != "inactive"
		if not joined:
			joined = getdate(today())
			self.report.add("warning", EMPLOYEES, row, f"{old_id}: no Join Date; today was used.")
		if end and end <= joined:
			self.report.add(
				"warning", EMPLOYEES, row, f"{old_id}: End Date {end} isn't after the Join Date {joined}; left empty."
			)
			end = None
		promoted = to_date(row.get("Promoted Date"))
		permanent = PERMANENT in (employment_type, EMPLOYMENT_TYPE_GUESSES.get(key(row.get("Type"))))
		if permanent and not text(row.get("Employment Status")):
			promoted, end = promoted or end, None  # the end of the first contract is when they became permanent
		elif active and end and end < getdate(today()):
			self.report.add(
				"info", EMPLOYEES, row,
				f"{old_id}: contract ended on {end} but they are imported as Active. Renew it, or set them to Left.",
			)
		if not active and not end:
			end = getdate(today())
			self.report.add("warning", EMPLOYEES, row, f"{old_id}: inactive without an End Date; today was used.")
		if text(row.get("Type")) and not employment_type:
			self.report.add(
				"warning", EMPLOYEES, row, f"{old_id}: Type '{text(row.get('Type'))}' isn't matched; left empty."
			)
		if text(row.get("Placement")) and not self.mapped("Placement", row.get("Placement")):
			self.report.add(
				"info", EMPLOYEES, row, f"{old_id}: Placement '{text(row.get('Placement'))}' isn't matched; left empty."
			)
		return {
			"employee_number": old_id,
			"company": self.company_of(row),
			"department": self.department(row.get("Team"), self.company_of(row)),
			"employment_type": employment_type,
			"designation": ensure_designation(text(row.get("Position"))),
			"branch": self.mapped("Placement", row.get("Placement")),
			"date_of_joining": joined,
			"contract_end_date": end if active and not permanent else None,
			"final_confirmation_date": promoted,
			"status": "Active" if active else "Left",
			"relieving_date": None if active else end,
			"company_email": mail if mail and not personal_mail else None,
			"personal_email": mail if personal_mail else None,
			"prefered_contact_email": ("Personal Email" if personal_mail else "Company Email") if mail else None,
			"cell_number": text(row.get("Phone Number")),
			"current_address": text(row.get("Address")),
			"marital_status": marital_status(row.get("Status Kawin")),
			"salary_mode": "Bank" if account else None,
			"bank_name": " - ".join(filter(None, (text(row.get("Bank")), text(row.get("Branch"))))),
			"bank_ac_no": account,
			"bank_account_name": text(row.get("Bank Account's Name")),
			"ktp_number": digits(row.get("Personal ID")),
			"npwp_number": text(row.get("NPWP")),
			"bpjs_kesehatan_number": digits(row.get("BPJS Kesehatan")),
			"bpjs_ketenagakerjaan_number": digits(row.get("BPJS Tenaga Kerja")),
			"personal_document_link": text(row.get("Personal Document Link")),
		}

	def create_employee(self, row):
		name = text(row.get("Name")) or text(row.get("Employee ID"))
		first, _, last = name.partition(" ")
		doc = frappe.new_doc("Employee")
		doc.update({k: v for k, v in self.employee_values(row).items() if v not in (None, "")})
		doc.first_name, doc.last_name = first, last
		if text(row.get("Business")) and not self.mapped("Business", row.get("Business")):
			self.report.add(
				"warning",
				EMPLOYEES,
				row,
				f"{text(row.get('Employee ID'))}: Business '{text(row.get('Business'))}' isn't matched; "
				f"put under {self.doc.default_company}.",
			)
		doc.flags.ignore_mandatory = True  # gender and date of birth aren't in the old sheets
		doc.insert(ignore_permissions=True)
		self.report.count("Employees created")
		return doc.name

	def fill_employee(self, employee, row, how):
		"""An employee already in Frappe: only empty fields are filled; company and status stay."""
		current = frappe.db.get_value("Employee", employee, "*", as_dict=True)
		values = self.employee_values(row)
		for field in ("company", "status", "relieving_date", "date_of_joining", "prefered_contact_email"):
			values.pop(field)
		if self.company_of(row) != current.company:  # the department must be of the company they stay in
			team = row.get("Team")
			values["department"] = self.department(team, current.company) or existing_department(text(team), current.company)
		filled = {
			field: value
			for field, value in values.items()
			if value not in (None, "") and current.get(field) in (None, "") and field in current
		}
		labels = sorted(frappe.get_meta("Employee").get_label(field) for field in filled)
		if filled:
			frappe.db.set_value("Employee", employee, filled)
		self.report.count("Employees already in Frappe (matched)")
		self.report.add(
			"info",
			EMPLOYEES,
			row,
			f"{text(row.get('Employee ID'))} {text(row.get('Name'))} = {employee} {current.employee_name} "
			f"(matched by {how}){'; filled in: ' + ', '.join(labels) if labels else ''}",
		)

	def company_of(self, row):
		return self.mapped("Business", row.get("Business")) or self.doc.default_company

	def prepare_departments(self, people, teams):
		"""Every old team's department in each company its people work for (a department belongs to one
		company), created up front so a failed row can't take one with it. A team without people: the
		default company's."""
		names = {}  # "People" and "people " are one team, also on Postgres, which compares case; A.02 spells it
		companies = defaultdict(set)
		for team in [text(r.get("Team Name")) for r in teams] + [text(r.get("Team")) for r in people]:
			if team:
				names.setdefault(key(team), team)
		for row in people:
			if text(row.get("Team")):
				companies[key(row.get("Team"))].add(self.company_of(row))
		for k, team in sorted(names.items()):
			for company in sorted(companies[k] or {self.doc.default_company}):
				self.each(TEAMS, [{"_row": ""}], lambda r, team=team, company=company: self.resolve_department(team, company))

	def resolve_department(self, team, company):
		"""HR's match if it is the company's; else the company's department of the matched or the old name."""
		matched = self.mapped("Team", team)
		matched_company, matched_name = (
			frappe.db.get_value("Department", matched, ["company", "department_name"]) if matched else (None, None)
		)
		department = (
			(matched if matched_company == company else None)
			or (existing_department(matched_name, company) if matched_name else None)
			or existing_department(team, company)
		)
		if not department:
			department = frappe.get_doc(
				{
					"doctype": "Department",
					"department_name": matched_name or team,
					"company": company,
					"parent_department": "All Departments",
				}
			).insert(ignore_permissions=True).name
			self.report.count("Departments created")
			self.report.add("info", TEAMS, "", f"New department {department} for the old team '{team}'.")
		self.departments[(key(team), company)] = department

	def department(self, team, company):
		return self.departments.get((key(team), company)) if text(team) else None

	def team_departments(self, team):
		"""Every company's department of an old team."""
		return sorted({d for (k, _company), d in self.departments.items() if k == key(team)})

	def link_supervisors(self, rows):
		"""Supervisor 1 (or 2) becomes Reports To, for employees who don't have one yet."""
		changed = False
		for row in rows:
			employee = self.employees.get(text(row.get("Employee ID")))
			if not employee or frappe.db.get_value("Employee", employee, "reports_to"):
				continue
			supervisor = self.employee_of(row.get("Supervisor 1 ID")) or self.employee_of(row.get("Supervisor 2 ID"))
			if supervisor == employee or not supervisor:
				continue
			frappe.db.set_value("Employee", employee, "reports_to", supervisor)
			self.report.count("Employees given their supervisor (Reports To)")
			changed = True
		if changed:
			# who-sees-whom follows the reporting tree; rebuild it once all links are in
			from frappe.utils.nestedset import rebuild_tree

			rebuild_tree("Employee")

	def employee_of(self, value):
		old_id = re.split(r"[,;\s]+", text(value))[0] if text(value) else ""
		return self.employee_id(old_id)

	def employee_id(self, old_id):
		"""The employee of an old ID: from the employee tab, else the one in Drea HR with that Employee Number."""
		if old_id in self.employees:
			return self.employees[old_id]
		if self.by_number is None:
			numbers = defaultdict(list)
			for e in frappe.get_all("Employee", fields=["name", "employee_number"]):
				numbers[text(e.employee_number)].append(e.name)
			self.by_number = {n: names[0] for n, names in numbers.items() if n and len(names) == 1}
		return self.by_number.get(old_id)

	# ------------------------------------------------------------ logins and approvers

	def create_logins(self, rows):
		for row in rows:
			employee, mail = self.employees.get(text(row.get("Employee ID"))), email(row.get("Email"))
			if not (employee and mail):
				continue
			current = frappe.db.get_value("Employee", employee, ["status", "user_id", "first_name", "last_name"], as_dict=True)
			if current.status != "Active" or current.user_id:
				continue
			self.each(EMPLOYEES, [row], lambda r, e=employee, c=current, m=mail: self.create_login(e, c, m, r))

	def create_login(self, employee, current, mail, row):
		roles = set(BASE_ROLES) | set(LOGIN_ROLES.get(key(row.get("HRIS Role")), []))
		if frappe.db.exists("User", mail):
			self.report.add("info", EMPLOYEES, row, f"{mail} already has a login; linked to {employee}, roles left as they are.")
			roles = set(frappe.get_roles(mail))
		else:
			frappe.get_doc(
				{
					"doctype": "User",
					"email": mail,
					"first_name": current.first_name,
					"last_name": current.last_name,
					"send_welcome_email": 0,
					"user_type": "System User",
					"roles": [{"role": r} for r in sorted(roles) if frappe.db.exists("Role", r)],
				}
			).insert(ignore_permissions=True)
			self.report.count("Logins created")
		doc = frappe.get_doc("Employee", employee)
		doc.user_id = mail
		# HR sees everyone; everyone else only themselves (their own User Permission)
		doc.create_user_permission = 0 if roles & HR_ROLES else 1
		doc.flags.ignore_mandatory = True
		doc.save(ignore_permissions=True)

	def set_leave_approvers(self, rows):
		"""A.02: a team's supervisors with a login approve its department's leave, if it has no approvers yet."""
		levels = bool(frappe.db.get_single_value("HR Settings", "leave_approval_by_levels"))
		for row, department in [(r, d) for r in rows for d in self.team_departments(r.get("Team Name"))]:
			doc = frappe.get_doc("Department", department)
			if doc.leave_approvers:
				self.report.add("info", TEAMS, row, f"{department} already has leave approvers; left as they are.")
				continue
			users = []
			for column in ("Supervisor 1 ID", "Supervisor 2 ID"):
				employee = self.employee_of(row.get(column))
				user = frappe.db.get_value("Employee", employee, "user_id") if employee else None
				if user and user not in users:
					users.append(user)
			if not users:
				self.report.add(
					"warning", TEAMS, row, f"{department}: no supervisor with a login; set its leave approvers by hand."
				)
				continue

			def save(r, doc=doc, users=users):
				for n, user in enumerate(users):
					approver = {"approver": user}
					if levels:
						approver["approval_level"] = "Required" if n == 0 else "Regular"
					doc.append("leave_approvers", approver)
					if not frappe.db.exists("Has Role", {"parent": user, "role": "Leave Approver"}):
						frappe.get_doc("User", user).add_roles("Leave Approver")
				doc.save(ignore_permissions=True)
				self.report.count("Departments given leave approvers")

			self.each(TEAMS, [row], save)

	# ------------------------------------------------------------ leave

	def import_balances(self, rows):
		"""C.01 -> allocations of the annual leave type. Duplicate rows keep the largest quota."""
		best = {}
		for row in rows:
			employee = self.employee_id(text(row.get("Employee ID")))
			start = to_date(row.get("Start Date"))
			year = int(to_number(row.get("Period (Y)"))) or (start.year if start else 0)
			if not employee or year < 2000:
				self.report.add("error", BALANCES, row, unknown(row, employee, ("Period (Y)", year >= 2000)))
				continue
			if year > getdate(today()).year:
				# the old HRIS keeps next year's row already; Drea HR gives that year's quota itself
				self.report.count("Leave balances of a year that hasn't started (left out)")
				continue
			total = to_number(row.get("Paid Leave Quota")) + to_number(row.get("Carried Over Quota"))
			if (employee, year) in best:
				self.report.add("warning", BALANCES, row, f"{employee}: a second {year} row; the larger quota is kept.")
				if total <= best[(employee, year)][1]:
					continue
			best[(employee, year)] = (row, total)

		leave_type = self.doc.annual_leave_type
		for (employee, year), (row, total) in sorted(best.items()):
			start = to_date(row.get("Start Date")) or date(year, 1, 1)
			end = to_date(row.get("End Date")) or date(year, 12, 31)
			if end < start:
				start, end = date(year, 1, 1), date(year, 12, 31)
			old_id = text(row.get("Leave Balance ID")) or f"{text(row.get('Employee ID'))}-{year}"
			if self.import_from and end < self.import_from:
				self.report.count("Leave balances before the start date (left out)")
			elif frappe.db.exists("Leave Allocation", {"old_hris_id": old_id, "docstatus": 1}):
				self.report.count("Leave balances already imported")
			elif not total:
				self.report.count("Leave balances of 0 days (nothing to allocate)")
			elif uses_leave_end_date(employee):
				self.report.count("Leave balances of employees without allocation (left out)")
			elif overlap := overlapping_allocation(employee, leave_type, start, end):
				self.report.add(
					"info", BALANCES, row, f"{employee} already has {overlap} for {leave_type} in that period; left as it is."
				)
			else:
				self.each(BALANCES, [row], lambda r, e=employee, s=start, t=end, n=total, o=old_id: self.allocate(e, s, t, n, o))

	def allocate(self, employee, start, end, total, old_id):
		doc = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee,
				"leave_type": self.doc.annual_leave_type,
				"from_date": start,
				"to_date": end,
				"new_leaves_allocated": total,
				# validation is skipped, so set what it would have worked out
				"total_leaves_allocated": total,
				"old_hris_id": old_id,
				"description": f"Old HRIS leave balance {old_id}",
			}
		)
		doc.flags.ignore_validate = True
		doc.insert(ignore_permissions=True)
		doc.submit()
		self.report.count("Leave balances (allocations)")

	def import_leave(self, rows):
		"""C.02, the approved leave. Personal: quota days as annual leave, the rest unpaid. Special: izin."""
		leave_from = self.leave_from()
		if rows and leave_from and leave_from < self.import_from:
			self.report.add(
				"info",
				LEAVE_LOG,
				"",
				f"Leave is imported from {leave_from}, the start of the leave year the start date falls in, "
				"so the leave balances add up.",
			)
		for row in rows:
			old_id = text(row.get("Leave Log ID"))
			employee = self.employee_id(text(row.get("Employee ID")))
			start = to_date(row.get("Start Date"))
			end = to_date(row.get("End Date")) or start
			if not (old_id and employee and start):
				self.report.add(
					"error", LEAVE_LOG, row, unknown(row, employee, ("Leave Log ID", old_id), ("Start Date", start))
				)
				continue
			if end < start:
				start, end = end, start
				self.report.add("warning", LEAVE_LOG, row, f"{old_id}: end date before start date; swapped.")
			if leave_from and end < leave_from:
				self.report.count("Leave before the start date (left out)")
				continue
			if self.not_employed(employee, start, end):
				self.report.count("Leave before the person joined or after they left (left out)")
				continue
			if frappe.db.exists("Leave Application", {"old_hris_id": ("in", (old_id, f"{old_id}-unpaid"))}):
				self.report.count("Leave already imported")
				continue
			if clash := overlapping_leave(employee, start, end):
				self.report.add(
					"error", LEAVE_LOG, row, f"{old_id}: {employee} already has leave {clash} on these dates; not imported."
				)
				continue
			self.each(LEAVE_LOG, [row], lambda r, e=employee, s=start, t=end, o=old_id: self.leave_row(r, e, s, t, o))

	def not_employed(self, employee, start, end=None):
		"""True when the days fall wholly before the joining date or after the relieving date."""
		if employee not in self.employment:
			self.employment[employee] = frappe.db.get_value("Employee", employee, ["date_of_joining", "relieving_date"])
		joined, left = self.employment[employee]
		end = end or start
		return bool((joined and end < getdate(joined)) or (left and start > getdate(left)))

	def leave_from(self):
		"""The start date, moved back to the start of the leave year it falls in: a balance is imported
		whole, so all the leave taken from it has to come in too, or Frappe shows days that were used."""
		if not self.import_from:
			return None
		starts = frappe.get_all(
			"Leave Allocation",
			filters={
				"leave_type": self.doc.annual_leave_type,
				"docstatus": 1,
				"from_date": ("<=", self.import_from),
				"to_date": (">=", self.import_from),
			},
			pluck="from_date",
		)
		return min([self.import_from, *map(getdate, starts)])

	def leave_row(self, row, employee, start, end, old_id):
		reason = text(row.get("Reason")) or text(row.get("Note"))
		if key(row.get("Type")) == "special":
			days = to_number(row.get("Used Special Leave")) or to_number(row.get("Total Leave Days"))
			parts = [(special_leave_type(reason, self.doc.other_leave_type), start, end, days)]
		else:
			paid, unpaid = to_number(row.get("Used Paid Leave")), to_number(row.get("Used Unpaid Leave"))
			if not paid and not unpaid:
				paid = to_number(row.get("Total Leave Days"))
			if paid and unpaid and end > start:
				# old records hold totals only: the paid days come first, the unpaid ones after
				paid_end = min(after_weekdays(start, paid), add_days(end, -1))
				parts = [
					(self.doc.annual_leave_type, start, paid_end, paid),
					(self.doc.unpaid_leave_type, add_days(paid_end, 1), end, unpaid),
				]
			else:
				parts = [(self.doc.annual_leave_type if paid else self.doc.unpaid_leave_type, start, end, paid + unpaid)]
		for n, (leave_type, from_date, to_date_, days) in enumerate(parts):
			self.insert_leave(employee, leave_type, from_date, to_date_, days, reason, row, old_id if n == 0 else f"{old_id}-unpaid")
		self.report.count("Leave records")

	def insert_leave(self, employee, leave_type, from_date, to_date_, days, reason, row, old_id):
		emp = frappe.db.get_value("Employee", employee, ["employee_name", "company", "department"], as_dict=True)
		half_day = from_date == to_date_ and 0 < days < 1
		doc = frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": employee,
				"employee_name": emp.employee_name,
				"company": emp.company,
				"department": emp.department,
				"leave_type": leave_type,
				"from_date": from_date,
				"to_date": to_date_,
				"half_day": int(half_day),
				"half_day_date": from_date if half_day else None,
				"total_leave_days": days or (to_date_ - from_date).days + 1,
				"description": reason,
				"status": "Approved",
				"posting_date": to_date(row.get("Timestamp")) or from_date,
				"follow_via_email": 0,
				"old_hris_id": old_id,
			}
		)
		doc.flags.ignore_validate = True
		doc.flags.old_hris_import = True
		# a check must not put events in a calendar that a rollback can't take back out
		doc.flags.skip_leave_calendar = self.dry_run
		doc.insert(ignore_permissions=True)
		doc.submit()
		self.report.count(f"Leave days as {leave_type}", days)

	# ------------------------------------------------------------ attendance

	def import_attendance(self, sheet, rows):
		"""B.01 rows -> Attendance plus its check-in/out. On Leave days come from the leave instead."""
		# Automatic Check-in people (directors...) are never absent; the tick is set before the import
		always_in = (
			set(frappe.get_all("Employee", filters={"auto_checkin": 1}, pluck="name"))
			if frappe.get_meta("Employee").has_field("auto_checkin")
			else set()
		)
		# one person with two rows for a day (an old ID and a new one): the row that isn't Absent counts
		came_in = {
			(self.employee_id(text(r.get("Employee ID"))), to_date(r.get("Date")))
			for r in rows
			if key(r.get("Status")) in ATTENDANCE_STATUS and key(r.get("Status")) != "absent"
		}

		def handle(row):
			employee = self.employee_id(text(row.get("Employee ID")))
			day = to_date(row.get("Date"))
			status = ATTENDANCE_STATUS.get(key(row.get("Status")))
			if key(row.get("Status")) in ATTENDANCE_SKIPPED:
				self.report.count(f"Attendance rows '{text(row.get('Status'))}' (not needed)")
				return
			if not (employee and day and status):
				self.report.add("error", sheet, row, unknown(row, employee, ("Date", day), ("Status", status)))
				return
			if key(row.get("Status")) == "absent" and employee in always_in:
				self.report.count("Absent days of people with Automatic Check-in (left out)")
				return
			if key(row.get("Status")) == "absent" and (employee, day) in came_in:
				self.report.count("Absent rows on a day the same person came in (left out)")
				return
			if self.import_from and day < self.import_from:
				self.report.count("Attendance before the start date (left out)")
				return
			if self.not_employed(employee, day):
				# the check Frappe makes, skipped with the rest of validation: else payroll counts these days
				self.report.count("Attendance before the person joined or after they left (left out)")
				return
			old_id = text(row.get("Attendance ID")) or f"{text(row.get('Employee ID'))}-{day}"
			if frappe.db.exists("Attendance", {"old_hris_id": old_id}):
				self.report.count("Attendance already imported")
				return
			if frappe.db.exists("Attendance", {"employee": employee, "attendance_date": day, "docstatus": ("!=", 2)}):
				self.report.count("Attendance days already in Frappe (left as they are)")
				return
			emp = frappe.db.get_value("Employee", employee, ["employee_name", "company", "department"], as_dict=True)
			attendance = frappe.get_doc(
				{
					"doctype": "Attendance",
					"employee": employee,
					"employee_name": emp.employee_name,
					"company": emp.company,
					"department": emp.department,
					"attendance_date": day,
					"status": status[0],
					"late_entry": status[1],
					"old_hris_id": old_id,
				}
			)
			attendance.flags.ignore_validate = True
			attendance.insert(ignore_permissions=True)
			attendance.submit()
			self.report.count("Attendance days")
			if status[1]:
				self.report.count("Attendance days late")
			latitude, longitude = to_latlong(row.get("Location"))
			for log_type, column in (("IN", "Check In Time"), ("OUT", "Check Out Time")):
				time = to_datetime(row.get(column), day)
				if time and not frappe.db.exists("Employee Checkin", {"employee": employee, "time": time}):
					checkin = frappe.get_doc(
						{
							"doctype": "Employee Checkin",
							"employee": employee,
							"time": time,
							"log_type": log_type,
							"attendance": attendance.name,
							"skip_auto_attendance": 1,
							"latitude": latitude if log_type == "IN" else None,
							"longitude": longitude if log_type == "IN" else None,
							"old_hris_photo_link": (text(row.get("Photo Link")) or None) if log_type == "IN" else None,
						}
					)
					checkin.flags.ignore_validate = True
					checkin.insert(ignore_permissions=True)
					self.report.count("Check-ins and check-outs")

		self.each(sheet, rows, handle)


# ---------------------------------------------------------------- lookups


class existing_employees:
	"""Employees already in Frappe, findable by old ID, email or exact full name."""

	def __init__(self):
		self.by_number, self.by_email, self.by_name = defaultdict(set), defaultdict(set), defaultdict(set)
		for e in frappe.get_all(
			"Employee",
			fields=["name", "employee_number", "employee_name", "user_id", "company_email", "personal_email"],
		):
			if e.employee_number:
				self.by_number[text(e.employee_number)].add(e.name)
			for mail in (e.user_id, e.company_email, e.personal_email):
				if email(mail):
					self.by_email[email(mail)].add(e.name)
			if e.employee_name:
				self.by_name[key(e.employee_name)].add(e.name)

	def find(self, old_id, mail, name):
		for how, found in (
			("old Employee ID", self.by_number.get(old_id)),
			("email", self.by_email.get(mail) if mail else None),
			("name", self.by_name.get(key(name)) if key(name) else None),
		):
			if found and len(found) > 1:
				return "ambiguous", f"{len(found)} employees in Frappe have the same {how} ({', '.join(sorted(found))})"
			if found:
				return next(iter(found)), how
		return None, None


def guess(doctype, old_value, default_company=None):
	"""A best guess for the matching table; only a single clear match is guessed."""
	k = key(old_value)
	if doctype == "Company":
		companies = frappe.get_all("Company", fields=["name", "abbr"])
		exact = [c.name for c in companies if k in (key(c.name), key(c.abbr))]
		if len(exact) == 1:
			return exact[0]
		partial = [c.name for c in companies if k and (k in key(c.name) or k in key(c.abbr))]
		return partial[0] if len(partial) == 1 else None
	if doctype == "Department":
		# a group (like Holding, over Director, Finance, HR) can hold people too; only the root can't
		found = frappe.get_all(
			"Department", filters={"name": ("!=", "All Departments")}, fields=["name", "department_name", "company", "is_group"]
		)
		same = [d for d in found if key(d.department_name) == k]
		if len(same) > 1:
			same = [d for d in same if d.company == default_company] or same
		if len(same) > 1:
			same = [d for d in same if not d.is_group]
		return same[0].name if len(same) == 1 else None
	if doctype == "Employment Type":
		name = EMPLOYMENT_TYPE_GUESSES.get(k)
		if name and frappe.db.exists("Employment Type", name):
			return name
	names = frappe.get_all(doctype, pluck="name")
	same = [n for n in names if key(n) == k]
	return same[0] if len(same) == 1 else None


def unknown(row, employee, *columns):
	"""Why a row can't be imported, naming each column at fault: (column, value it gave or None)."""
	problems = [] if employee else [f"unknown Employee ID '{text(row.get('Employee ID'))}'"]
	for column, value in columns:
		if not value:
			given = text(row.get(column))
			if column == "Status" and given:
				problems.append(f"Status '{given}' isn't one the import knows ({', '.join(STATUS_WORDS)})")
			else:
				problems.append(f"{column} '{given}' can't be read" if given else f"no {column}")
	return "Not imported: " + "; ".join(problems) + "."


def special_leave_type(reason, fallback):
	reason = reason.lower()
	types = frappe.get_all("Leave Type", pluck="name")
	for word, type_word in SPECIAL_LEAVE_WORDS:
		if word not in reason:
			continue
		found = [t for t in types if type_word in t.lower() and (type_word != "melahirkan" or "istri" not in t.lower())]
		if found:
			return sorted(found, key=len)[0]
	return fallback


def overlapping_leave(employee, start, end):
	return frappe.db.get_value(
		"Leave Application",
		{
			"employee": employee,
			"docstatus": ("<", 2),
			"status": ("in", ("Open", "Approved")),
			"from_date": ("<=", end),
			"to_date": (">=", start),
		},
	)


def overlapping_allocation(employee, leave_type, start, end):
	return frappe.db.get_value(
		"Leave Allocation",
		{
			"employee": employee,
			"leave_type": leave_type,
			"docstatus": 1,
			"from_date": ("<=", end),
			"to_date": (">=", start),
		},
	)


def marital_status(value):
	words = re.findall(r"[a-z]+", text(value).lower())
	for word, status in MARITAL_WORDS:
		if any(w == word or (len(word) > 2 and w.startswith(word)) for w in words):
			return status
	return None


def existing_department(team, company):
	"""The company's department of that name, compared like the old values (Postgres compares case)."""
	if not key(team):
		return None
	found = sorted(
		(d.department_name != team, d.name)  # the exact spelling first
		for d in frappe.get_all("Department", filters={"company": company}, fields=["name", "department_name"])
		if key(d.department_name) == key(team)
	)
	return found[0][1] if found else None


def ensure_designation(name):
	"""The designation of that name in any case ("designer" = "Designer"), created if there is none."""
	if not name:
		return None
	same = sorted(d for d in frappe.get_all("Designation", pluck="name") if d.lower() == name.lower())
	if name in same:
		return name
	if same:
		return same[0]
	frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(ignore_permissions=True)
	return name


def after_weekdays(start, count):
	"""Roughly where the paid part of a leave ends: the count-th weekday from the start."""
	day, left = start, max(int(count + 0.5), 1)
	while True:
		if day.weekday() < 5:
			left -= 1
			if left <= 0:
				return day
		day = add_days(day, 1)


def file_path(file_url):
	return frappe.get_doc("File", {"file_url": file_url}).get_full_path()


def file_name(file_url):
	return file_url.rsplit("/", 1)[-1]


def error_text(e):
	message = strip_html(str(e)) or e.__class__.__name__
	return re.sub(r"\s+", " ", message).strip()[:300]

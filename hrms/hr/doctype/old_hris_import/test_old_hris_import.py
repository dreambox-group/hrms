# Copyright (c) 2026, Dreambox and contributors
# See license.txt

import io
import json
from unittest.mock import patch

import openpyxl

import frappe
from frappe.utils import getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.old_hris_import.importer import OldHRISImporter
from hrms.tests.utils import HRMSTestSuite

COMPANY = "_Test Company"
ANNUAL, UNPAID, SICK, OTHER = "_Test Old Annual", "_Test Old Unpaid", "_Test Izin Sakit", "_Test Old Izin"
EMPLOYEE_HEADERS = [
	"Employee ID", "Name", "Type", "Position", "Business", "Placement", "Team", "Supervisor 1 ID",
	"Supervisor 2 ID", "Join Date", "End Date", "Employment Status", "HRIS Role", "Email", "Phone Number",
	"Personal ID", "NPWP", "Bank", "Account Number", "Bank Account's Name", "Branch",
]
ATTENDANCE_HEADERS = ["Attendance ID", "Employee ID", "Date", "Status", "Location", "Check In Time", "Check Out Time", "Photo Link"]


def workbook(sheets):
	book = openpyxl.Workbook()
	book.remove(book.active)
	for name, (headers, rows) in sheets.items():
		sheet = book.create_sheet(name)
		sheet.append(headers)
		for row in rows:
			sheet.append([row.get(h) for h in headers])
	out = io.BytesIO()
	book.save(out)
	return out.getvalue()


def attach(name, content):
	return frappe.get_doc({"doctype": "File", "file_name": name, "content": content, "is_private": 1}).insert().file_url


def old_hris_workbook():
	people = [
		{"Employee ID": "90001", "Name": "Andi Saputra", "Type": "Full Time - Permanent", "Position": "Designer",
		 "Business": "_Test Company", "Team": "Old Team Alpha", "Supervisor 1 ID": "90002", "Join Date": "1/15/2024",
		 "Employment Status": "Active", "HRIS Role": "Member", "Email": "andi.old@example.com", "Personal ID": "3201-0000-1111",
		 "NPWP": "12.345.678.9-012.000", "Bank": "BCA", "Account Number": "123456", "Bank Account's Name": "Andi S"},
		{"Employee ID": "90002", "Name": "Budi Santoso", "Type": "Full Time - Contract", "Business": "_Test Company",
		 "Team": "Old Team Alpha", "Join Date": "2/1/2023", "End Date": "12/31/2027", "Employment Status": "Active",
		 "HRIS Role": "Manager", "Email": "budi.old@example.com"},
		{"Employee ID": "90003", "Name": "Citra Pergi", "Type": "Intern", "Business": "Somewhere Unknown",
		 "Team": "Old Team Alpha", "Join Date": "1/2/2025", "End Date": "6/30/2025", "Employment Status": "Inactive"},
		{"Employee ID": "90004", "Name": "Dewi Existing", "Business": "_Test Company", "Join Date": "3/3/2022",
		 "Employment Status": "Active", "Personal ID": "3300"},
		{"Employee ID": "90001", "Name": "Andi Twice"},
	]
	teams = [{"Team Name": "Old Team Alpha", "Supervisor 1 ID": "90002"}]
	balances = [{"Leave Balance ID": "LB-1", "Employee ID": "90001", "Period (Y)": 2025, "Paid Leave Quota": 12,
	             "Carried Over Quota": 2, "Start Date": "1/1/2025", "End Date": "12/31/2025"}]
	leave = [
		{"Leave Log ID": "LR-1", "Employee ID": "90001", "Type": "Personal", "Start Date": "3/3/2025", "End Date": "3/5/2025", "Used Paid Leave": 3, "Reason": "Liburan"},
		{"Leave Log ID": "LR-2", "Employee ID": "90001", "Type": "Personal", "Start Date": "4/7/2025", "End Date": "4/10/2025", "Used Paid Leave": 2, "Used Unpaid Leave": 2},
		{"Leave Log ID": "LR-3", "Employee ID": "90002", "Type": "Special", "Start Date": "5/6/2025", "End Date": "5/6/2025", "Used Special Leave": 1, "Reason": "Sakit demam"},
		{"Leave Log ID": "LR-4", "Employee ID": "90002", "Type": "Special", "Start Date": "5/12/2025", "Total Leave Days": 1, "Reason": "Urusan keluarga"},
		{"Leave Log ID": "LR-5", "Employee ID": "99999", "Type": "Personal", "Start Date": "5/12/2025", "Used Paid Leave": 1},
	]
	attendance = [
		{"Attendance ID": "ATD-1", "Employee ID": "90001", "Date": "3/10/2025", "Status": "Present", "Location": "-6.1, 106.8", "Check In Time": "08:55:00", "Check Out Time": "17:01:00", "Photo Link": "https://drive.example/p1"},
		{"Attendance ID": "ATD-2", "Employee ID": "90001", "Date": "3/11/2025", "Status": "Late", "Check In Time": "09:45:00"},
		{"Attendance ID": "ATD-3", "Employee ID": "90002", "Date": "3/10/2025", "Status": "On Leave"},
		{"Attendance ID": "ATD-4", "Employee ID": "90001", "Date": "3/12/2025", "Status": "Absent"},
	]
	balance_headers = ["Leave Balance ID", "Employee ID", "Period (Y)", "Paid Leave Quota", "Carried Over Quota", "Start Date", "End Date"]
	leave_headers = ["Leave Log ID", "Employee ID", "Type", "Start Date", "End Date", "Total Leave Days", "Used Paid Leave", "Used Unpaid Leave", "Used Special Leave", "Reason", "Timestamp"]
	return workbook(
		{
			"A.01. Employee Database": (EMPLOYEE_HEADERS, people),
			"A.02. Team Database": (["Team ID", "Team Name", "Supervisor 1 ID", "Supervisor 2 ID"], teams),
			"B.01. Attendance": (ATTENDANCE_HEADERS, attendance),
			"C.01. Leave Balance": (balance_headers, balances),
			"C.02. Leave Log": (leave_headers, leave),
		}
	)


class TestOldHRISImport(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)
		for name, values in (
			(ANNUAL, {}),
			(UNPAID, {"is_lwp": 1}),
			(SICK, {"allow_negative": 1}),
			(OTHER, {"allow_negative": 1}),
		):
			if not frappe.db.exists("Leave Type", name):
				frappe.get_doc({"doctype": "Leave Type", "leave_type_name": name, **values}).insert()
		self.dewi = make_employee("dewi.existing@example.com", COMPANY, first_name="Dewi Existing")
		frappe.db.set_value("Employee", self.dewi, {"employee_name": "Dewi Existing", "employee_number": None})
		archive = workbook(
			{"Jan": (ATTENDANCE_HEADERS, [{"Attendance ID": "ATD-0", "Employee ID": "90002", "Date": "1/6/2025", "Status": "Present", "Check In Time": "08:30:00"}])}
		)
		self.doc = frappe.get_doc(
			{
				"doctype": "Old HRIS Import",
				"workbook": attach("old-hris.xlsx", old_hris_workbook()),
				"attendance_files": [{"file": attach("2025.xlsx", archive)}],
				"default_company": COMPANY,
				"create_logins": 1,
				"annual_leave_type": ANNUAL,
				"unpaid_leave_type": UNPAID,
				"other_leave_type": OTHER,
			}
		).insert()
		# the job commits as it goes; the test's own rollback must stay possible
		self.no_commit = patch.object(frappe.db, "commit", lambda *a, **k: None)
		self.no_commit.start()

	def tearDown(self):
		self.no_commit.stop()
		super().tearDown()

	def report(self):
		self.doc.reload()
		return json.loads(self.doc.report)

	def employee(self, old_id):
		return frappe.db.get_value("Employee", {"employee_number": old_id})

	def test_check_saves_nothing_and_fills_the_matching(self):
		# outside tests, a new login queues its contact job for after the commit; it must not outlive the check
		queued = []
		create_employee = OldHRISImporter.create_employee

		def create_and_queue(importer, row):
			frappe.db.after_commit.add(lambda: queued.append(row))
			return create_employee(importer, row)

		with patch.object(OldHRISImporter, "create_employee", create_and_queue):
			self.doc.check()
		frappe.db.after_commit.run()
		self.assertEqual(queued, [])
		report = self.report()
		self.assertEqual(self.doc.status, "Checked", report.get("failed"))
		self.assertTrue(report["dry_run"])
		self.assertEqual(report["counts"]["Employees created"], 3)
		self.assertEqual(report["counts"]["Leave records"], 4)

		# nothing stayed behind
		self.assertFalse(self.employee("90001"))
		self.assertFalse(frappe.db.exists("Department", {"department_name": "Old Team Alpha"}))
		self.assertFalse(frappe.db.exists("Leave Application", {"old_hris_id": "LR-1"}))
		self.assertFalse(frappe.db.exists("User", "andi.old@example.com"))
		self.assertIsNone(frappe.db.get_value("Employee", self.dewi, "employee_number"))

		mapping = {(row.column, row.old_value): row.maps_to for row in self.doc.mappings}
		self.assertEqual(mapping[("Business", "_Test Company")], COMPANY)
		self.assertIsNone(mapping[("Business", "Somewhere Unknown")])
		self.assertIn(("Team", "Old Team Alpha"), mapping)

		# changing the matching means checking again
		self.doc.mappings[0].maps_to = None
		self.doc.save()
		self.assertRaises(frappe.ValidationError, self.doc.start_import)

	def test_import_and_run_again(self):
		self.doc.check()
		self.doc.reload()
		self.doc.start_import()
		report = self.report()
		self.assertEqual(self.doc.status, "Imported", report.get("failed"))

		andi, budi, citra = self.employee("90001"), self.employee("90002"), self.employee("90003")
		self.assertTrue(andi and budi and citra)
		andi_doc = frappe.get_doc("Employee", andi)
		self.assertEqual(andi_doc.department, frappe.db.get_value("Department", {"department_name": "Old Team Alpha"}))
		self.assertEqual(andi_doc.reports_to, budi)
		self.assertEqual(andi_doc.ktp_number, "320100001111")
		self.assertEqual(andi_doc.bank_account_name, "Andi S")
		self.assertEqual(andi_doc.user_id, "andi.old@example.com")
		self.assertEqual(getdate(andi_doc.date_of_joining), getdate("2024-01-15"))
		citra_doc = frappe.get_doc("Employee", citra)
		self.assertEqual((citra_doc.status, str(citra_doc.relieving_date), citra_doc.company), ("Left", "2025-06-30", COMPANY))

		# matched by name: only the empty fields were filled
		dewi = frappe.get_doc("Employee", self.dewi)
		self.assertEqual((dewi.employee_number, dewi.ktp_number), ("90004", "3300"))

		# the team's supervisor approves the new department's leave
		department = frappe.get_doc("Department", andi_doc.department)
		self.assertEqual([row.approver for row in department.leave_approvers], ["budi.old@example.com"])

		leave = {
			row.old_hris_id: row
			for row in frappe.get_all(
				"Leave Application",
				filters={"old_hris_id": ("is", "set")},
				fields=["old_hris_id", "leave_type", "from_date", "to_date", "total_leave_days", "status", "docstatus"],
			)
		}
		self.assertEqual(leave["LR-1"].leave_type, ANNUAL)
		self.assertEqual((leave["LR-2"].leave_type, leave["LR-2"].total_leave_days), (ANNUAL, 2))
		self.assertEqual((leave["LR-2-unpaid"].leave_type, str(leave["LR-2-unpaid"].from_date)), (UNPAID, "2025-04-09"))
		self.assertEqual(leave["LR-3"].leave_type, SICK)
		self.assertEqual(leave["LR-4"].leave_type, OTHER)
		self.assertTrue(all(row.docstatus == 1 and row.status == "Approved" for row in leave.values()))
		self.assertEqual(
			frappe.db.get_value("Leave Allocation", {"old_hris_id": "LB-1"}, "total_leaves_allocated"), 14
		)
		# history doesn't notify anyone
		self.assertFalse(frappe.db.exists("PWA Notification", {"reference_document_type": "Leave Application", "to_user": "andi.old@example.com"}))

		attendance = frappe.get_all(
			"Attendance", filters={"old_hris_id": ("is", "set")}, fields=["old_hris_id", "status", "late_entry"]
		)
		self.assertEqual(
			sorted((a.old_hris_id, a.status, a.late_entry) for a in attendance),
			[("ATD-0", "Present", 0), ("ATD-1", "Present", 0), ("ATD-2", "Present", 1), ("ATD-4", "Absent", 0)],
		)
		self.assertEqual(frappe.db.count("Employee Checkin", {"employee": andi}), 3)
		self.assertEqual(
			frappe.db.get_value("Employee Checkin", {"employee": andi, "log_type": "IN", "time": "2025-03-10 08:55:00"}, "old_hris_photo_link"),
			"https://drive.example/p1",
		)

		errors = [m[3] for m in report["messages"] if m[0] == "error"]
		self.assertTrue(any("90001 appears twice" in e for e in errors))
		self.assertTrue(any("99999" in e for e in errors))
		warnings = [m[3] for m in report["messages"] if m[0] == "warning"]
		self.assertTrue(any("Somewhere Unknown" in w for w in warnings))

		# a second run brings in nothing new
		counts = {
			doctype: frappe.db.count(doctype)
			for doctype in ("Employee", "Leave Application", "Leave Allocation", "Attendance", "Employee Checkin", "User", "Department")
		}
		self.doc.reload()
		self.doc.check()
		self.doc.reload()
		self.doc.start_import()
		report = self.report()
		self.assertEqual(self.doc.status, "Imported", report.get("failed"))
		self.assertEqual(report["counts"]["Leave already imported"], 4)
		self.assertEqual(report["counts"]["Attendance already imported"], 4)
		self.assertNotIn("Employees created", report["counts"])
		for doctype, n in counts.items():
			self.assertEqual(frappe.db.count(doctype), n, doctype)

	def test_start_date_keeps_the_whole_leave_year(self):
		# a balance is imported whole, so leave taken from it before the start date must come in too
		self.doc.import_from = "2025-04-01"
		self.doc.save()
		self.doc.check()
		self.doc.reload()
		self.doc.start_import()
		report = self.report()
		self.assertEqual(self.doc.status, "Imported", report.get("failed"))

		self.assertTrue(frappe.db.exists("Leave Application", {"old_hris_id": "LR-1", "docstatus": 1}))  # 3 March
		self.assertTrue(frappe.db.exists("Leave Allocation", {"old_hris_id": "LB-1", "docstatus": 1}))
		self.assertTrue(any("imported from 2025-01-01" in m[3] for m in report["messages"]))
		# attendance keeps the start date as it is
		self.assertFalse(frappe.db.exists("Attendance", {"old_hris_id": ("in", ("ATD-0", "ATD-1", "ATD-2", "ATD-4"))}))
		self.assertEqual(report["counts"]["Attendance before the start date (left out)"], 4)

	def test_values_differing_only_in_case_are_one(self):
		# Postgres compares case: "Old Team Beta" and "old team beta " must still be one department
		people = [
			{"Employee ID": "91001", "Name": "Eka Satu", "Team": "old team beta ", "Position": "designer", "Join Date": "1/6/2025", "Employment Status": "Active"},
			{"Employee ID": "91002", "Name": "Fani Dua", "Team": "Old Team Beta", "Position": "Designer", "Join Date": "1/6/2025", "Employment Status": "Active"},
		]
		if not frappe.db.exists("Designation", "Designer"):
			frappe.get_doc({"doctype": "Designation", "designation_name": "Designer"}).insert()
		content = workbook(
			{
				"A.01 Employee Database": (EMPLOYEE_HEADERS, people),
				"A.02 Team Database": (["Team ID", "Team Name", "Supervisor 1 ID"], [{"Team Name": "Old Team Beta"}]),
			}
		)
		self.doc.workbook = attach("case.xlsx", content)
		self.doc.attendance_files = []
		self.doc.save()
		self.doc.check()
		self.doc.reload()
		self.assertEqual([row.old_value for row in self.doc.mappings if row.column == "Team"], ["Old Team Beta"])
		self.doc.start_import()
		report = self.report()
		self.assertEqual(self.doc.status, "Imported", report.get("failed"))

		eka, fani = (frappe.get_doc("Employee", self.employee(i)) for i in ("91001", "91002"))
		self.assertEqual(eka.department, fani.department)
		self.assertEqual(frappe.db.get_value("Department", eka.department, "department_name"), "Old Team Beta")
		names = frappe.get_all("Department", pluck="department_name") + frappe.get_all("Designation", pluck="name")
		self.assertEqual([n for n in names if n.lower() in ("old team beta", "designer")].count("Old Team Beta"), 1)
		self.assertNotIn("old team beta", names)
		self.assertEqual((eka.designation, fani.designation), ("Designer", "Designer"))
		self.assertNotIn("designer", names)

	def test_each_company_has_its_own_department_and_dreambox_employment_types(self):
		# Dreambox: a department belongs to the CV its people work for; the old Type maps to the four types
		other = "_Test Company 1"
		for name in ("Full-time Permanent", "Full-time Contract", "Freelance"):
			if not frappe.db.exists("Employment Type", name):
				frappe.get_doc({"doctype": "Employment Type", "employee_type_name": name}).insert()
		accounts = {}
		for company in (COMPANY, other):
			accounts[company] = frappe.get_doc(
				{"doctype": "Department", "department_name": "Old Account", "company": company, "parent_department": "All Departments"}
			).insert().name
		people = [
			{"Employee ID": "92001", "Name": "Gita Tiga", "Type": "Full Time - Permanent", "Business": COMPANY, "Team": "Old Digital",
			 "Join Date": "1/6/2025", "End Date": "12/31/2027", "Employment Status": "Active", "Email": "gita.old@example.com"},
			{"Employee ID": "92002", "Name": "Hadi Empat", "Type": "Freelancer", "Business": other, "Team": "old digital",
			 "Join Date": "1/6/2025", "Employment Status": "Active"},
			{"Employee ID": "92003", "Name": "Indah Lima", "Type": "Contract", "Business": other, "Team": "Old Marketing",
			 "Join Date": "1/6/2025", "End Date": "12/31/2027", "Employment Status": "Active"},
		]
		content = workbook(
			{
				"A.01 Employee Database": (EMPLOYEE_HEADERS, people),
				"A.02 Team Database": (["Team ID", "Team Name", "Supervisor 1 ID"], [{"Team Name": "Old Digital", "Supervisor 1 ID": "92001"}]),
			}
		)
		self.doc.workbook = attach("cvs.xlsx", content)
		self.doc.attendance_files = []
		self.doc.save()
		self.doc.check()
		self.doc.reload()
		guessed = {(row.column, row.old_value): row.maps_to for row in self.doc.mappings}
		self.assertEqual(guessed[("Type", "Full Time - Permanent")], "Full-time Permanent")
		self.assertEqual(guessed[("Type", "Freelancer")], "Freelance")
		self.assertEqual(guessed[("Type", "Contract")], "Full-time Contract")
		# HR matches the renamed team to the department of one CV; the other CV's of that name is used for its people
		for row in self.doc.mappings:
			if (row.column, row.old_value) == ("Team", "Old Marketing"):
				row.maps_to = accounts[COMPANY]
		self.doc.save()
		self.doc.check()
		self.doc.reload()
		self.doc.start_import()
		report = self.report()
		self.assertEqual(self.doc.status, "Imported", report.get("failed"))

		gita, hadi, indah = (frappe.get_doc("Employee", self.employee(i)) for i in ("92001", "92002", "92003"))
		self.assertEqual(
			[(e.company, e.employment_type) for e in (gita, hadi, indah)],
			[(COMPANY, "Full-time Permanent"), (other, "Freelance"), (other, "Full-time Contract")],
		)
		for e in (gita, hadi):
			self.assertEqual(frappe.db.get_value("Department", e.department, ["company", "department_name"]), (e.company, "Old Digital"))
		self.assertEqual(indah.department, accounts[other])
		self.assertIsNone(gita.contract_end_date)
		self.assertEqual(str(indah.contract_end_date), "2027-12-31")
		# the team's supervisor approves leave in both CVs' departments
		for e in (gita, hadi):
			approvers = [r.approver for r in frappe.get_doc("Department", e.department).leave_approvers]
			self.assertEqual(approvers, ["gita.old@example.com"])

	def test_without_the_employee_tab_rows_go_to_employee_numbers_in_drea_hr(self):
		# HR can leave the employee tab out: leave and attendance go to the people already there
		frappe.db.set_value("Employee", self.dewi, "employee_number", "93001")
		next_year = getdate().year + 1
		balance_headers = ["Leave Balance ID", "Employee ID", "Period (Y)", "Paid Leave Quota", "Carried Over Quota", "Start Date", "End Date"]
		leave_headers = ["Leave Log ID", "Employee ID", "Type", "Start Date", "End Date", "Total Leave Days", "Used Paid Leave", "Used Unpaid Leave", "Used Special Leave", "Reason"]
		content = workbook(
			{
				"A.02. Team Database": (["Team ID", "Team Name", "Supervisor 1 ID"], [{"Team Name": "Old Team Gone", "Supervisor 1 ID": "93001"}]),
				"B.01. Attendance": (ATTENDANCE_HEADERS, [
					{"Attendance ID": "ATD-93", "Employee ID": 93001, "Date": "3/10/2025", "Status": "Present", "Check In Time": "08:55:00"},
					{"Attendance ID": "ATD-94", "Employee ID": "10999", "Date": "3/10/2025", "Status": "Present"},
				]),
				"C.01. Leave Balance": (balance_headers, [
					{"Leave Balance ID": "LB-93", "Employee ID": 93001, "Period (Y)": "2025", "Paid Leave Quota": 12, "Carried Over Quota": 0, "Start Date": "1/1/2025", "End Date": "12/31/2025"},
					{"Leave Balance ID": "LB-94", "Employee ID": 93001, "Period (Y)": str(next_year), "Paid Leave Quota": 12, "Carried Over Quota": 0, "End Date": f"12/31/{next_year}"},
				]),
				"C.02. Leave Log": (leave_headers, [
					{"Leave Log ID": "LR-93", "Employee ID": 93001, "Type": "Personal", "Start Date": "3/4/2025", "End Date": "3/4/2025", "Used Paid Leave": 1},
				]),
			}
		)
		self.doc.workbook = attach("no-employees.xlsx", content)
		self.doc.attendance_files = []
		self.doc.save()
		self.doc.check()
		self.doc.reload()
		self.assertEqual([row.old_value for row in self.doc.mappings if row.column == "Team"], [])
		self.doc.start_import()
		report = self.report()
		self.assertEqual(self.doc.status, "Imported", report.get("failed"))

		self.assertEqual(frappe.db.get_value("Attendance", {"old_hris_id": "ATD-93"}, "employee"), self.dewi)
		self.assertEqual(frappe.db.get_value("Leave Allocation", {"old_hris_id": "LB-93"}, "employee"), self.dewi)
		self.assertEqual(frappe.db.get_value("Leave Application", {"old_hris_id": "LR-93"}, "employee"), self.dewi)
		self.assertFalse(frappe.db.exists("Leave Allocation", {"old_hris_id": "LB-94"}))
		self.assertEqual(report["counts"]["Leave balances of a year that hasn't started (left out)"], 1)
		self.assertFalse(frappe.db.exists("Department", {"department_name": "Old Team Gone"}))
		self.assertTrue(any("unknown Employee ID '10999'" in m[3] for m in report["messages"]))

	def test_absent_is_left_out_for_automatic_check_in_and_days_with_a_second_row(self):
		frappe.db.set_value("Employee", self.dewi, {"employee_number": "93002", "auto_checkin": 1})
		budi = make_employee("budi.absent@example.com", COMPANY, first_name="Budi Absent")
		frappe.db.set_value("Employee", budi, "employee_number", "93003")
		content = workbook(
			{
				"B.01. Attendance": (ATTENDANCE_HEADERS, [
					{"Attendance ID": "ATD-A1", "Employee ID": "93002", "Date": "3/10/2025", "Status": "Absent"},
					# the same person under an old and a new ID, now both 93003: the check-in wins over Absent
					{"Attendance ID": "ATD-A2", "Employee ID": "93003", "Date": "3/10/2025", "Status": "Absent"},
					{"Attendance ID": "ATD-A3", "Employee ID": "93003", "Date": "3/10/2025", "Status": "Present", "Check In Time": "08:50:00"},
					{"Attendance ID": "ATD-A4", "Employee ID": "93003", "Date": "3/11/2025", "Status": "Absent"},
				]),
			}
		)
		self.doc.workbook = attach("absent.xlsx", content)
		self.doc.attendance_files = []
		self.doc.save()
		self.doc.check()
		self.doc.reload()
		self.doc.start_import()
		report = self.report()
		self.assertEqual(self.doc.status, "Imported", report.get("failed"))

		self.assertFalse(frappe.db.exists("Attendance", {"employee": self.dewi}))
		self.assertEqual(
			frappe.get_all("Attendance", filters={"employee": budi}, fields=["old_hris_id", "status"], order_by="attendance_date"),
			[{"old_hris_id": "ATD-A3", "status": "Present"}, {"old_hris_id": "ATD-A4", "status": "Absent"}],
		)
		self.assertEqual(report["counts"]["Absent days of people with Automatic Check-in (left out)"], 1)
		self.assertEqual(report["counts"]["Absent rows on a day the same person came in (left out)"], 1)

	def test_todays_employee_sheet_after_a_reset(self):
		# the employee tab as HR keeps it now: other titles, Status Kawin, no Active/Inactive column
		from hrms.hr.doctype.old_hris_import import reset_employees

		frappe.db.set_value("Employee", self.dewi, "employee_number", "94009")
		checkin = frappe.get_doc({"doctype": "Employee Checkin", "employee": self.dewi, "time": "2025-03-10 08:00:00", "log_type": "IN"}).insert().name
		reset_employees.run(confirm=frappe.local.site, only=[self.dewi])
		self.assertFalse(frappe.db.exists("Employee", self.dewi))
		self.assertFalse(frappe.db.exists("Employee Checkin", checkin))
		self.assertTrue(frappe.db.exists("Leave Type", ANNUAL))  # the leave setup stays

		headers = ["Employee Number", "Name", "Status", "Designation", "Division", "Legal Entity", "Join Date", "Promoted",
			"End Date", "Email", "NIK", "Status Kawin", "Basic Salary", "Take Home Pay", "Supervisor 1", "Supervisor 2"]
		people = [
			{"Employee Number": 94001, "Name": "Joko Enam", "Status": "Full-time Permanent", "Designation": "Director", "Division": "Old Holding",
			 "Legal Entity": COMPANY, "Join Date": "1/2/2020", "End Date": "4/1/2020", "Email": "joko.old@example.com", "NIK": "3201-0000-2222", "Status Kawin": "K/1"},
			{"Employee Number": 94002, "Name": "Kiki Tujuh", "Status": "Full-time Contract", "Designation": "Content", "Division": "Old Holding",
			 "Legal Entity": COMPANY, "Join Date": "1/2/2025", "End Date": "12/31/2099", "Status Kawin": "Belum Kawin",
			 "Basic Salary": 1, "Take Home Pay": 1, "Supervisor 1": 94001},
			{"Employee Number": 94003, "Name": "Lala Delapan", "Status": "Intern", "Division": "Old Holding", "Legal Entity": COMPANY,
			 "Join Date": "1/2/2024", "End Date": "6/30/2024", "Status Kawin": "TK/0"},
			{"Employee Number": 94004, "Name": "Mira Sembilan", "Status": "Full-time Contract", "Division": "Old Holding", "Legal Entity": COMPANY,
			 "Join Date": "10/23/2025", "End Date": "4/30/2025"},  # a typo: ends before joining
		]
		# Holding is a group over Director, Finance, HR: the matching still guesses it
		holding = frappe.get_doc(
			{"doctype": "Department", "department_name": "Old Holding", "company": COMPANY, "is_group": 1,
			 "parent_department": "All Departments"}
		).insert().name
		self.doc.workbook = attach("today.xlsx", workbook({"Employee Database": (headers, people)}))
		self.doc.attendance_files = []
		self.doc.save()
		self.doc.check()
		self.doc.reload()
		self.assertEqual(
			[r.maps_to for r in self.doc.mappings if (r.column, r.old_value) == ("Team", "Old Holding")], [holding]
		)
		# a row left empty (from before) is filled on the next check
		for r in self.doc.mappings:
			if r.old_value == "Old Holding":
				r.maps_to = None
		self.doc.save()
		self.doc.check()
		self.doc.reload()
		self.assertEqual(
			[r.maps_to for r in self.doc.mappings if (r.column, r.old_value) == ("Team", "Old Holding")], [holding]
		)
		self.doc.start_import()
		report = self.report()
		self.assertEqual(self.doc.status, "Imported", report.get("failed"))

		joko, kiki, lala, mira = (frappe.get_doc("Employee", self.employee(i)) for i in ("94001", "94002", "94003", "94004"))
		self.assertEqual((joko.designation, joko.ktp_number, joko.marital_status), ("Director", "320100002222", "Married"))
		self.assertEqual((kiki.reports_to, kiki.status, str(kiki.contract_end_date), kiki.marital_status), (joko.name, "Active", "2099-12-31", "Single"))
		# today's sheet lists the people working now: a passed End Date is a contract to renew, not a leaving date
		self.assertEqual((lala.status, str(lala.contract_end_date), lala.marital_status), ("Active", "2024-06-30", "Single"))
		self.assertIn("contract ended on 2024-06-30", str(report))
		# a permanent's End Date is when the first contract ended: they became permanent then
		self.assertEqual((str(joko.final_confirmation_date), joko.contract_end_date, joko.status), ("2020-04-01", None, "Active"))
		self.assertEqual((mira.status, mira.contract_end_date, mira.relieving_date), ("Active", None, None))
		self.assertEqual(kiki.department, holding)
		self.assertEqual(joko.user_id, "joko.old@example.com")

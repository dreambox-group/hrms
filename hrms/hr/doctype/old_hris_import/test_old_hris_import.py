# Copyright (c) 2026, Dreambox and contributors
# See license.txt

import io
import json
from unittest.mock import patch

import openpyxl

import frappe
from frappe.utils import getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

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
		self.doc.check()
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

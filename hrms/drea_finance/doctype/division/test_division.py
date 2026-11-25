# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.drea_finance.doctype.division.division import next_division_code


class TestDivision(IntegrationTestCase):
	def setUp(self):
		for name in frappe.get_all("Division", pluck="name"):
			self._detach(name)
			frappe.delete_doc("Division", name, force=True)

	def _detach(self, division):
		frappe.db.delete("Drea Finance Department", {"division": division})
		frappe.clear_document_cache("Drea Finance Settings", "Drea Finance Settings")

	def test_code_is_generated_from_the_highest_existing_number(self):
		self.assertEqual(next_division_code(), "DV-00001")
		first = frappe.get_doc({"doctype": "Division", "division_name": "Digital"}).insert()
		self.assertEqual(first.name, "DV-00001")
		self.assertEqual(first.division_code, "DV-00001")

		# a code imported from Drea Finance is kept as it is, and the series continues after it
		imported = frappe.get_doc(
			{"doctype": "Division", "division_code": "dv-00007", "division_name": "Mind Sequence"}
		).insert()
		self.assertEqual(imported.name, "DV-00007")
		third = frappe.get_doc({"doctype": "Division", "division_name": "Website"}).insert()
		self.assertEqual(third.name, "DV-00008")

	def test_shared_and_bad_codes(self):
		shared = frappe.get_doc(
			{"doctype": "Division", "division_code": "SHARED", "division_name": "Support staff"}
		).insert()
		self.assertEqual(shared.name, "SHARED")
		for bad in ("dv 1", "1DV", "DV-00001-with-a-very-long-suffix"):
			with self.assertRaises(frappe.ValidationError):
				frappe.get_doc({"doctype": "Division", "division_code": bad, "division_name": "x"}).insert()

	def test_code_cannot_change(self):
		doc = frappe.get_doc({"doctype": "Division", "division_name": "Digital"}).insert()
		doc.division_code = "DV-00099"
		self.assertRaises(frappe.ValidationError, doc.save)

	def map_department(self, division):
		company = frappe.get_all("Company", limit=1, pluck="name")[0]
		dept = frappe.get_doc(
			{"doctype": "Department", "department_name": "_Test Finance Division Dept", "company": company}
		).insert(ignore_if_duplicate=True)
		dept = frappe.get_doc("Department", {"department_name": "_Test Finance Division Dept", "company": company})
		settings = frappe.get_single("Drea Finance Settings")
		settings.set("departments", [r for r in settings.departments if r.department != dept.name])
		settings.append("departments", {"department": dept.name, "division": division})
		settings.save()
		return settings, dept

	def test_deactivation_refused_while_mapped_to_a_department(self):
		division = frappe.get_doc({"doctype": "Division", "division_name": "Digital"}).insert()
		settings, dept = self.map_department(division.name)
		division.reload()
		division.is_active = 0
		self.assertRaises(frappe.ValidationError, division.save)

		settings.set("departments", [r for r in settings.departments if r.department != dept.name])
		settings.save()
		division.reload()
		division.is_active = 0
		division.save()
		self.assertEqual(frappe.db.get_value("Division", division.name, "is_active"), 0)

	def test_mapping_refuses_an_inactive_division(self):
		division = frappe.get_doc({"doctype": "Division", "division_name": "Old", "is_active": 0}).insert()
		self.assertRaises(frappe.ValidationError, self.map_department, division.name)

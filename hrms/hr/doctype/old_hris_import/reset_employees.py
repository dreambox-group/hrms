# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Removes every employee and what belongs to them, so the employee sheet can be imported fresh.

Kept: logins (User; the import links them again by email), companies, departments, designations,
and the leave and attendance setup (leave types and policies, holiday lists, shift types, HR Settings).
Removed: employees and every record that points to one (attendance, check-ins, leave, assignments...).

Look first (nothing is changed):
	bench --site <site> execute hrms.hr.doctype.old_hris_import.reset_employees.run
Then remove, after a backup, by naming the site:
	bench --site <site> execute hrms.hr.doctype.old_hris_import.reset_employees.run --kwargs '{"confirm": "<site>"}'
"""

from collections import Counter

import frappe


def run(confirm=None, only=None):
	employees = only or frappe.get_all("Employee", pluck="name")  # only: a few, for tests
	plan = linked_records(employees)
	print(f"Employees: {len(employees)}")
	for (doctype, _field), names in sorted(plan.items()):
		print(f"  {doctype}: {len(names)}")
	if confirm != frappe.local.site:
		print(f'Nothing changed. To remove all of the above, pass --kwargs \'{{"confirm": "{frappe.local.site}"}}\'.')
		return

	frappe.flags.in_import = True  # no emails, no calendar events
	done = Counter()
	for (doctype, _field), names in sorted(plan.items()):
		for name in names:
			doc = frappe.get_doc(doctype, name)
			if doc.docstatus == 1:
				doc.flags.ignore_links = True
				doc.cancel()
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)
			done[doctype] += 1
	frappe.db.delete("User Permission", {"allow": "Employee", "for_value": ("in", employees or [""])})
	# Reports To links them to each other; unlink first so the tree lets each go
	frappe.db.set_value("Employee", {"reports_to": ("in", employees)}, "reports_to", None, update_modified=False)
	for name in employees:
		frappe.delete_doc("Employee", name, force=True, ignore_permissions=True, delete_permanently=True)
		done["Employee"] += 1
	frappe.db.commit()
	frappe.flags.in_import = False
	print("Removed:", dict(done))


def linked_records(employees):
	"""(doctype, field) -> names of the documents whose Link field points to one of the employees."""
	if not employees:
		return {}
	fields = frappe.get_all("DocField", filters={"fieldtype": "Link", "options": "Employee"}, fields=["parent", "fieldname"])
	fields += frappe.get_all("Custom Field", filters={"fieldtype": "Link", "options": "Employee"}, fields=["dt as parent", "fieldname"])
	plan = {}
	for f in fields:
		meta = frappe.get_meta(f.parent)
		if f.parent == "Employee" or meta.issingle or meta.istable or meta.is_virtual or not frappe.db.table_exists(f.parent):
			continue  # child rows go with their parent document; Reports To is handled above
		names = frappe.get_all(f.parent, filters={f.fieldname: ("in", employees)}, pluck="name")
		if names:
			plan.setdefault((f.parent, f.fieldname), []).extend(names)
	# a document found through two fields is removed once
	seen = set()
	for key in sorted(plan):
		plan[key] = [n for n in plan[key] if (key[0], n) not in seen and not seen.add((key[0], n))]
	return {k: v for k, v in plan.items() if v}

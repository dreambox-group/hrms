# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

import hashlib
import json
import traceback
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

RUNNING = ("Checking", "Importing")


class OldHRISImport(Document):
	def onload(self):
		self.set_onload("needs_check", self.checked_fingerprint != self.fingerprint())

	def validate(self):
		before = self.get_doc_before_save()
		if before and before.status in RUNNING and not self.flags.from_job:
			frappe.throw(_("Wait for the {0} to finish before changing anything.").format(before.status.lower()))

	def fingerprint(self) -> str:
		"""What a check was run on: the files' contents, the options and the matching table."""
		files = [self.workbook] + [row.file for row in self.attendance_files]
		hashes = [frappe.db.get_value("File", {"file_url": url}, "content_hash") or url for url in files if url]
		state = [
			hashes,
			[self.default_company, str(self.import_from or ""), int(self.create_logins or 0)],
			[self.annual_leave_type, self.unpaid_leave_type, self.other_leave_type],
			sorted([row.column, row.old_value, row.maps_to or ""] for row in self.mappings),
		]
		return hashlib.sha256(json.dumps(state, default=str).encode()).hexdigest()

	@frappe.whitelist()
	def check(self):
		"""A full dry run: everything is imported and then rolled back. Fills the matching table."""
		self.start("Checking", dry_run=True)

	@frappe.whitelist()
	def start_import(self):
		if self.status not in ("Checked", "Imported") or self.checked_fingerprint != self.fingerprint():
			frappe.throw(
				_("Something changed since the last check (a file, an option or the matching). Check again first."),
				title=_("Check first"),
			)
		self.start("Importing", dry_run=False)

	def start(self, status, dry_run):
		frappe.only_for(("HR Manager", "System Manager"))
		if self.status in RUNNING:
			frappe.throw(_("Already {0}.").format(self.status.lower()))
		self.db_set("status", status)
		frappe.enqueue(
			run_job,
			name=self.name,
			dry_run=dry_run,
			queue="long",
			timeout=3600,
			enqueue_after_commit=True,
			now=frappe.flags.in_test,
		)


def run_job(name, dry_run):
	from hrms.hr.doctype.old_hris_import.importer import OldHRISImporter

	doc = frappe.get_doc("Old HRIS Import", name)
	frappe.flags.in_import = True
	frappe.flags.mute_emails = True
	try:
		importer = OldHRISImporter(doc, dry_run=dry_run)
		if dry_run:
			# the matching table is the one thing a check keeps
			importer.refresh_mappings()
			doc.flags.from_job = True
			doc.save(ignore_permissions=True)
			frappe.db.commit()
			with nothing_saved():
				report = importer.run()
		else:
			report = importer.run()
			frappe.db.commit()
		status = "Checked" if dry_run else "Imported"
	except Exception:
		frappe.db.rollback()
		doc.log_error(f"Old HRIS Import {'check' if dry_run else 'import'} failed")
		report = {"failed": traceback.format_exc(limit=-6)}
		status = "Failed"
	finally:
		frappe.flags.in_import = False
		frappe.flags.mute_emails = False

	report["dry_run"] = dry_run
	report["finished"] = str(now_datetime())
	values = {"status": status, "report": json.dumps(report, default=str)}
	if status == "Checked":
		doc.reload()
		values.update(checked_fingerprint=doc.fingerprint(), checked_on=now_datetime())
	elif status == "Imported":
		values["imported_on"] = now_datetime()
	frappe.db.set_value("Old HRIS Import", name, values)
	frappe.db.commit()
	frappe.publish_realtime("old_hris_import_done", {"name": name}, doctype="Old HRIS Import", docname=name)


@contextmanager
def nothing_saved():
	"""Rolls everything back at the end, and stops any code inside from committing on the way.

	A savepoint, not a full rollback, so only the dry run is undone. Anything that commits
	implicitly would release it, and the rollback would then fail loudly instead of passing quietly.
	"""
	commit = frappe.db.commit
	frappe.db.commit = lambda *args, **kwargs: None
	frappe.db.savepoint("old_hris_check")
	try:
		yield
	finally:
		frappe.db.commit = commit
		frappe.db.rollback(save_point="old_hris_check")


@frappe.whitelist()
def get_defaults():
	"""Sensible first choices for a new import."""
	frappe.only_for(("HR Manager", "System Manager"))
	leave_types = frappe.get_all("Leave Type", fields=["name", "is_lwp", "allow_negative"])
	annual = frappe.get_all(
		"Leave Policy Detail", filters={"parenttype": "Leave Policy"}, pluck="leave_type", limit=1
	) or frappe.get_all("Leave Allocation", filters={"docstatus": 1}, pluck="leave_type", limit=1)
	return {
		"default_company": frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company"),
		"annual_leave_type": annual[0] if annual else None,
		"unpaid_leave_type": next((t.name for t in leave_types if t.is_lwp), None),
		"other_leave_type": next((t.name for t in leave_types if t.allow_negative and not t.is_lwp), None),
	}

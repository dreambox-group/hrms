# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Supporting documents for leave (e.g. a doctor's note) that may only arrive after the request.

Leave types with "Requires a Supporting Document" give the request a Document Due date. It can be
approved before the document is attached; until then the employee and the approvers are reminded.
"""

import base64
import binascii
from mimetypes import guess_type

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, today

from hrms.hr.doctype.leave_application.leave_calendar import get_leave_label

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
DOCUMENT_TYPES = ("image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf")
CORRECTION_ROLES = ("HR Manager", "HR User", "System Manager")


def get_leave_attachments(leave_applications: list[str]) -> dict[str, list[dict]]:
	if not leave_applications:
		return {}
	attachments = {}
	for file in frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Leave Application", "attached_to_name": ("in", leave_applications)},
		fields=["name", "file_name", "file_url", "is_private", "attached_to_name"],
		order_by="creation",
	):
		attachments.setdefault(file.attached_to_name, []).append(file)
	return attachments


def get_missing_documents(filters: dict | None = None) -> list[dict]:
	"""Leave requests whose supporting document is due but not attached yet."""
	applications = frappe.get_all(
		"Leave Application",
		filters={
			**(filters or {}),
			"document_due_date": ("is", "set"),
			"docstatus": ("!=", 2),
			"status": ("not in", ["Rejected", "Cancelled"]),
		},
		fields=[
			"name",
			"employee",
			"employee_name",
			"leave_type",
			"from_date",
			"to_date",
			"document_due_date",
		],
		order_by="document_due_date",
	)
	attached = get_leave_attachments([a.name for a in applications])
	date = getdate(today())
	missing = []
	for application in applications:
		if application.name in attached:
			continue
		application.label = get_leave_label(application.employee, application.leave_type)
		application.overdue = getdate(application.document_due_date) < date
		missing.append(application)
	return missing


def get_missing_documents_for(user: str) -> dict:
	"""The user's own leave missing a document, and leave they approve that is missing one."""
	employees = frappe.get_all("Employee", filters={"user_id": user}, pluck="name")
	mine = get_missing_documents({"employee": ("in", employees)}) if employees else []

	approving = set(
		frappe.get_all(
			"Leave Application", filters={"leave_approver": user, "docstatus": ("!=", 2)}, pluck="name"
		)
	)
	approving.update(
		frappe.get_all(
			"Leave Application Approver",
			filters={"parenttype": "Leave Application", "approver": user},
			pluck="parent",
		)
	)
	to_review = get_missing_documents({"name": ("in", list(approving))}) if approving else []
	return {"mine": mine, "to_review": [a for a in to_review if a.employee not in employees]}


@frappe.whitelist(methods=["POST"])
def upload_leave_document(leave_application: str, filename: str, content: str) -> dict:
	"""Attaches a supporting document to a leave request, also after it was approved.

	Only the employee whose leave it is, or HR, may upload.
	"""
	doc = frappe.get_doc("Leave Application", leave_application)
	user = frappe.session.user
	is_hr = bool(set(CORRECTION_ROLES) & set(frappe.get_roles(user)))
	if frappe.db.get_value("Employee", doc.employee, "user_id") != user and not is_hr:
		frappe.throw(_("Only the employee can add documents to their leave request."), frappe.PermissionError)
	if doc.docstatus == 2:
		frappe.throw(_("This leave request was cancelled."))

	content_type = guess_type(filename)[0]
	if content_type not in DOCUMENT_TYPES:
		frappe.throw(_("Upload a photo (JPG, PNG) or a PDF."))

	if content.startswith("data:"):
		content = content.split(",", 1)[-1]
	try:
		data = base64.b64decode(content, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The file could not be read. Please try again."))
	if len(data) > MAX_DOCUMENT_BYTES:
		frappe.throw(_("The file is too large (10 MB at most)."))

	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": data,
			"is_private": 1,
			"attached_to_doctype": "Leave Application",
			"attached_to_name": doc.name,
		}
	).insert(ignore_permissions=True)
	doc.add_comment("Attachment", _("Supporting document added: {0}").format(file.file_name))
	return {"name": file.name, "file_name": file.file_name, "file_url": file.file_url}


def remind_missing_leave_documents() -> None:
	"""Daily: reminds employees whose leave still needs its supporting document."""
	for application in get_missing_documents():
		user = frappe.db.get_value("Employee", application.employee, "user_id")
		if not user:
			continue
		due = formatdate(application.document_due_date)
		message = (
			_("The supporting document for your {0} leave ({1}) was due on {2}. Please upload it.")
			if application.overdue
			else _("Please upload the supporting document for your {0} leave ({1}) by {2}.")
		).format(frappe.bold(application.label), formatdate(application.from_date), due)
		frappe.get_doc(
			{
				"doctype": "PWA Notification",
				"to_user": user,
				"from_user": "Administrator",
				"message": message,
				"reference_document_type": "Leave Application",
				"reference_document_name": application.name,
			}
		).insert(ignore_permissions=True)

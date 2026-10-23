# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Supporting documents for leave (e.g. a doctor's note) that may only arrive after the request.

Leave types on HR Settings' "Leave Types that need a Supporting Document" list mark the request as
needing one. There is no deadline: it can be approved first, and until the employee uploads the
document a reminder stays on the dashboard of the employee, the approvers who approved it, and HR.
"""

import base64
import binascii
from mimetypes import guess_type

import frappe
from frappe import _

from hrms.hr.doctype.leave_application.leave_calendar import get_leave_label

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
DOCUMENT_TYPES = ("image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf")
CORRECTION_ROLES = ("HR Manager", "HR User", "System Manager")
SETTINGS_FIELD = "leave_types_requiring_document"


def get_leave_types_requiring_document() -> set[str]:
	return set(
		frappe.get_all(
			"HR Settings Leave Type",
			filters={"parenttype": "HR Settings", "parentfield": SETTINGS_FIELD},
			pluck="leave_type",
		)
	)


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
	"""Leave requests that need a supporting document and don't have one attached yet."""
	applications = frappe.get_all(
		"Leave Application",
		filters={
			**(filters or {}),
			"document_required": 1,
			"docstatus": ("!=", 2),
			"status": ("not in", ["Rejected", "Cancelled"]),
		},
		fields=["name", "employee", "employee_name", "leave_type", "from_date", "to_date", "status"],
		order_by="from_date",
	)
	attached = get_leave_attachments([a.name for a in applications])
	missing = []
	for application in applications:
		if application.name in attached:
			continue
		application.label = get_leave_label(application.employee, application.leave_type)
		missing.append(application)
	return missing


def get_approved_by(user: str) -> list[str]:
	"""Leave requests the user approved: as the chosen Leave Approver, or with their vote."""
	approved = set(
		frappe.get_all(
			"Leave Application",
			filters={"leave_approver": user, "status": "Approved", "docstatus": 1},
			pluck="name",
		)
	)
	approved.update(
		frappe.get_all(
			"Leave Application Approver",
			filters={"parenttype": "Leave Application", "approver": user, "decision": "Approved"},
			pluck="parent",
		)
	)
	return list(approved)


def get_missing_documents_for(user: str) -> dict:
	"""Missing documents on the user's dashboard: their own, the leave they approved, and for HR all."""
	employees = frappe.get_all("Employee", filters={"user_id": user}, pluck="name")
	mine = get_missing_documents({"employee": ("in", employees)}) if employees else []
	shown = {a.name for a in mine}

	approved = get_approved_by(user)
	to_review = [
		a
		for a in (get_missing_documents({"name": ("in", approved)}) if approved else [])
		if a.name not in shown
	]
	shown.update(a.name for a in to_review)

	hr = []
	if set(CORRECTION_ROLES) & set(frappe.get_roles(user)):
		hr = [a for a in get_missing_documents() if a.name not in shown]
	return {"mine": mine, "to_review": to_review, "hr": hr}


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

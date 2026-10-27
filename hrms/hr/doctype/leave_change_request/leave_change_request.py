# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Asking to cancel or move an approved leave.

The employee talks to HR first (the request's checklist says so), then sends the request. Nothing
changes until HR approves it: then the leave is cancelled, and for new dates a leave with those dates
takes its place (amended from the old one, keeping its approvers' decisions).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import bold, cint, formatdate, getdate, now_datetime

CANCEL = "Cancel the leave"
CHANGE = "Change the dates"
HR_ROLES = ("HR Manager", "HR User", "System Manager")


class LeaveChangeRequestError(frappe.ValidationError):
	pass


class LeaveChangeRequest(Document):
	def validate(self):
		if self.is_new() or self.status == "Open":
			self.validate_leave()
			self.validate_checklist()
		self.validate_dates()
		if not self.flags.deciding and self.has_value_changed("status") and not self.is_new():
			frappe.throw(_("Use Approve or Reject to decide on this request."), LeaveChangeRequestError)

	def validate_leave(self):
		leave = frappe.db.get_value(
			"Leave Application", self.leave_application, ["docstatus", "status"], as_dict=True
		)
		if not leave or leave.docstatus != 1 or leave.status != "Approved":
			frappe.throw(_("Only approved leave can be changed or cancelled."), LeaveChangeRequestError)

		if frappe.db.exists(
			"Leave Change Request",
			{"leave_application": self.leave_application, "status": "Open", "name": ("!=", self.name)},
		):
			frappe.throw(
				_("This leave already has a change request waiting for HR."), LeaveChangeRequestError
			)

	def validate_checklist(self):
		if not (cint(self.informed_hr) and cint(self.understands_waiting)):
			frappe.throw(
				_("Tick both items on the checklist first: tell HR before sending this request."),
				LeaveChangeRequestError,
			)

	def validate_dates(self):
		if self.change != CHANGE:
			self.new_from_date = self.new_to_date = None
			return

		if not (self.new_from_date and self.new_to_date):
			frappe.throw(_("Pick the new dates."), LeaveChangeRequestError)
		if getdate(self.new_to_date) < getdate(self.new_from_date):
			frappe.throw(_("The new end date can't be before the new start date."), LeaveChangeRequestError)
		if getdate(self.new_from_date) == getdate(self.from_date) and getdate(self.new_to_date) == getdate(
			self.to_date
		):
			frappe.throw(_("The new dates are the same as the leave's dates."), LeaveChangeRequestError)

	@frappe.whitelist()
	def decide(self, decision: str, note: str | None = None):
		if not set(HR_ROLES) & set(frappe.get_roles()):
			frappe.throw(_("Only HR can decide on leave change requests."), frappe.PermissionError)
		if self.status != "Open":
			frappe.throw(_("This request is already {0}.").format(_(self.status)), LeaveChangeRequestError)
		if decision not in ("Approved", "Rejected"):
			frappe.throw(_("Approve or reject the request."), LeaveChangeRequestError)

		frappe.db.savepoint("leave_change")
		try:
			if decision == "Approved":
				self.apply()
			self.status = decision
			self.decided_by = frappe.session.user
			self.decided_on = now_datetime()
			self.hr_note = note
			self.flags.deciding = True
			self.save(ignore_permissions=True)
		except Exception:
			# the leave stays as it was when its new version can't be made (balance, overlap, ...)
			frappe.db.rollback(save_point="leave_change")
			raise

		self.notify_employee()
		return self.status

	def apply(self):
		leave = frappe.get_doc("Leave Application", self.leave_application)
		if leave.docstatus != 1 or leave.status != "Approved":
			frappe.throw(_("The leave is no longer approved."), LeaveChangeRequestError)

		leave.flags.ignore_permissions = True
		leave.add_comment("Info", _("Cancelled through {0}").format(self.name))
		leave.cancel()
		if self.change == CHANGE:
			self.new_leave_application = make_leave_with_new_dates(leave, self).name

	def notify_employee(self):
		user = frappe.db.get_value("Employee", self.employee, "user_id")
		if not user or user == frappe.session.user:
			return
		what = (
			_("cancel your leave")
			if self.change == CANCEL
			else _("move your leave to {0}").format(dates(self.new_from_date, self.new_to_date))
		)
		frappe.get_doc(
			{
				"doctype": "PWA Notification",
				"from_user": frappe.session.user,
				"to_user": user,
				"message": _("HR {0} your request to {1}").format(bold(_(self.status).lower()), what),
				"reference_document_type": "Leave Application",
				"reference_document_name": self.new_leave_application or self.leave_application,
			}
		).insert(ignore_permissions=True)


def make_leave_with_new_dates(leave, request):
	"""The approved leave with the new dates, keeping the old one's approvers and their decisions."""
	new = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"amended_from": leave.name,
			"employee": leave.employee,
			"leave_type": leave.leave_type,
			"company": leave.company,
			"from_date": request.new_from_date,
			"to_date": request.new_to_date,
			# a half day only carries over to a new single day
			"half_day": cint(leave.half_day and request.new_from_date == request.new_to_date),
			"half_day_date": request.new_from_date
			if leave.half_day and request.new_from_date == request.new_to_date
			else None,
			"description": leave.description,
			"posting_date": leave.posting_date,
			"leave_approver": leave.leave_approver,
			"leave_approver_name": leave.leave_approver_name,
			"status": "Approved",
			"approvers": [
				{
					"approver": row.approver,
					"approver_name": row.approver_name,
					"approval_level": row.approval_level,
					"department": row.department,
					"decision": row.decision,
					"decided_on": row.decided_on,
				}
				for row in leave.get("approvers", [])
			],
		}
	)
	new.flags.leave_change_request = request.name
	new.flags.ignore_permissions = True
	new.insert()
	copy_attachments(leave.name, new.name)
	new.submit()
	new.add_comment(
		"Info",
		_("Dates changed by HR through {0}: was {1}").format(
			request.name, dates(leave.from_date, leave.to_date)
		),
	)
	return new


def copy_attachments(from_leave: str, to_leave: str) -> None:
	for file in frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Leave Application", "attached_to_name": from_leave},
		fields=["file_url", "file_name", "is_private"],
	):
		frappe.get_doc(
			{
				"doctype": "File",
				"file_url": file.file_url,
				"file_name": file.file_name,
				"is_private": file.is_private,
				"attached_to_doctype": "Leave Application",
				"attached_to_name": to_leave,
			}
		).insert(ignore_permissions=True)


def dates(from_date, to_date) -> str:
	if getdate(from_date) == getdate(to_date):
		return formatdate(from_date)
	return f"{formatdate(from_date)} – {formatdate(to_date)}"


def get_open_requests(company: str | None = None) -> list[dict]:
	"""Open change requests for the HR Dashboard, oldest first."""
	filters = {"status": "Open"}
	if company:
		filters["company"] = company
	return frappe.get_all(
		"Leave Change Request",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"department",
			"leave_type",
			"from_date",
			"to_date",
			"change",
			"new_from_date",
			"new_to_date",
			"reason",
			"creation",
		],
		order_by="creation",
	)

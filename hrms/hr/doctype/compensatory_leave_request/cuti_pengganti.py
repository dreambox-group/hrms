# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Cuti Pengganti: days off earned by working overtime or on a day off.

The employee names the day they worked (a Compensatory Leave Request of the leave type set in HR
Settings). Their supervisors approve it the way they approve leave, and each approved day is added to
that leave type. The days can be used until N months after the day worked (HR Settings, 3 by default):
worked 1 Sep, approved 1 Oct, usable until 1 Dec. Unused days then expire.

An employee's Cuti Pengganti days all sit on one long-running Leave Allocation. Each request keeps its
own expiry: leave taken uses the days that expire first, and a daily job takes what is left of an
expired request off the allocation (a negative Leave Ledger Entry from the day after it expires).
Compensatory Leave Requests of other leave types work as in stock Frappe HR.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, add_years, cint, date_diff, flt, format_date, getdate, today

from hrms.hr.supervisors import get_supervisors
from hrms.hr.utils import create_additional_leave_ledger_entry

HR_ROLES = ("HR Manager", "HR User", "System Manager")
# the allocation that carries an employee's Cuti Pengganti days; each request's days expire on their own
CARRIER_YEARS = 10


class CutiPenggantiError(frappe.ValidationError):
	pass


def get_settings() -> tuple[str | None, int]:
	leave_type, months = frappe.db.get_value(
		"HR Settings", None, ["compensatory_leave_type", "compensatory_leave_expiry_months"]
	)
	return leave_type, cint(months)


def get_leave_type() -> str | None:
	return get_settings()[0]


def is_cuti_pengganti(leave_type: str | None) -> bool:
	return bool(leave_type) and leave_type == get_leave_type()


def expiry_for(work_date) -> str | None:
	"""Usable up to and including this date: N months after the day worked."""
	months = get_settings()[1]
	return add_months(getdate(work_date), months) if months > 0 else None


def request_days(doc) -> float:
	days = date_diff(doc.work_end_date, doc.work_from_date) + 1
	return days - 0.5 if cint(doc.half_day) else days


def is_hr(user: str | None = None) -> bool:
	return bool(set(HR_ROLES) & set(frappe.get_roles(user or frappe.session.user)))


# --- the request -----------------------------------------------------------------------------------


def validate_request(doc) -> None:
	"""Compensatory Leave Request validate, for the Cuti Pengganti leave type (stock refuses future days)."""
	from hrms.hr.doctype.leave_application.leave_end_date import uses_leave_end_date

	employment_type = frappe.db.get_value("Employee", doc.employee, "employment_type")
	if uses_leave_end_date(doc.employee, employment_type):
		frappe.throw(
			_(
				"{0} employees get no leave allocation (HR Settings: Employee Types without Leave Allocation), so they can't get Cuti Pengganti."
			).format(frappe.bold(employment_type)),
			exc=CutiPenggantiError,
		)

	doc.expires_on = expiry_for(doc.work_from_date)
	if doc.docstatus != 0:
		return

	# only the approvers' decisions (or HR in the desk) set the status
	if not doc.flags.cuti_pengganti_decision and not is_hr():
		doc.status = "Open"
	set_approvers(doc)


def set_approvers(doc) -> None:
	"""The employee's current supervisors; decisions already made are kept (read from the database)."""
	decided = {}
	if not doc.is_new():
		decided = {
			(row.approver, row.approval_level): row
			for row in frappe.get_all(
				"Leave Application Approver",
				filters={"parent": doc.name, "parenttype": doc.doctype, "decision": ("!=", "Pending")},
				fields=["approver", "approver_name", "approval_level", "department", "decision", "decided_on"],
				order_by="idx",
			)
		}

	doc.set("approvers", [])
	for approver in get_supervisors(doc.employee):
		doc.append("approvers", decided.pop((approver.approver, approver.approval_level), None) or approver)
	for row in decided.values():
		doc.append("approvers", row)


def get_outcome(doc) -> str | None:
	"""Rejected as soon as anyone rejects; approved once every Required supervisor and, if there are
	any, one Regular supervisor approve (the same rule as leave)."""
	decisions = [row.decision for row in doc.approvers]
	if "Rejected" in decisions:
		return "Rejected"
	required = [row.decision for row in doc.approvers if row.approval_level == "Required"]
	regular = [row.decision for row in doc.approvers if row.approval_level != "Required"]
	if (
		"Approved" in decisions
		and all(d == "Approved" for d in required)
		and (not regular or "Approved" in regular)
	):
		return "Approved"
	return None


def record_decision(doc, decision: str) -> str:
	if doc.docstatus != 0 or doc.status != "Open":
		frappe.throw(_("This request is already {0}.").format(_(doc.status)), exc=CutiPenggantiError)

	user = frappe.session.user
	row = next((r for r in doc.approvers if r.approver == user and r.decision == "Pending"), None)
	if not row:
		if any(r.approver == user for r in doc.approvers):
			frappe.throw(_("You have already decided on this request."), exc=CutiPenggantiError)
		frappe.throw(_("You are not a supervisor of this employee."), frappe.PermissionError)

	# Regular supervisors decide as one group, as with leave
	if row.approval_level != "Required" and any(
		r.approval_level != "Required" and r.decision != "Pending" for r in doc.approvers
	):
		frappe.throw(_("Another supervisor has already decided on this request."), exc=CutiPenggantiError)

	if decision == "Approved" and doc.expires_on and getdate(doc.expires_on) < getdate(today()):
		frappe.throw(
			_("The days for {0} expired on {1}, so they can't be approved any more.").format(
				format_date(doc.work_from_date), format_date(doc.expires_on)
			),
			exc=CutiPenggantiError,
		)

	row.db_set({"decision": decision, "decided_on": frappe.utils.now_datetime()})
	doc.add_comment(
		"Info",
		_("{0} ({1} supervisor): {2}").format(row.approver_name or user, _(row.approval_level), _(decision)),
	)

	if outcome := get_outcome(doc):
		doc.status = outcome
		doc.flags.cuti_pengganti_decision = True
		# checked against the supervisors above, who may not have submit rights themselves
		doc.flags.ignore_permissions = True
		doc.submit()
	return doc.status


def before_submit(doc) -> None:
	if doc.status not in ("Approved", "Rejected"):
		frappe.throw(_("Approve or reject the request before submitting it."), exc=CutiPenggantiError)
	if not doc.flags.cuti_pengganti_decision and not is_hr():
		frappe.throw(_("Only the employee's supervisors or HR can decide on this request."), frappe.PermissionError)
	if doc.status == "Approved" and doc.expires_on and getdate(doc.expires_on) < getdate(today()):
		frappe.throw(
			_("The days for {0} expired on {1}, so they can't be approved any more.").format(
				format_date(doc.work_from_date), format_date(doc.expires_on)
			),
			exc=CutiPenggantiError,
		)


def on_submit(doc) -> None:
	if doc.status != "Approved":
		return
	days = request_days(doc)
	allocation = get_carrier_allocation(doc, days)
	doc.db_set("leave_allocation", allocation.name)
	if allocation.flags.created_for_request:
		expire_unused(doc.employee)
		return

	allocation.new_leaves_allocated = flt(allocation.new_leaves_allocated) + days
	allocation.validate()
	allocation.db_set("new_leaves_allocated", allocation.total_leaves_allocated)
	allocation.db_set("total_leaves_allocated", allocation.total_leaves_allocated)
	create_additional_leave_ledger_entry(allocation, days, credit_from(doc, allocation))
	expire_unused(doc.employee)


def on_cancel(doc) -> None:
	if doc.status != "Approved" or not doc.leave_allocation:
		return
	allocation = frappe.get_doc("Leave Allocation", doc.leave_allocation)
	valid_from = credit_from(doc, allocation)
	days = request_days(doc)
	allocation.new_leaves_allocated = max(flt(allocation.new_leaves_allocated) - days, 0)
	allocation.validate()
	allocation.db_set("new_leaves_allocated", allocation.total_leaves_allocated)
	allocation.db_set("total_leaves_allocated", allocation.total_leaves_allocated)
	create_additional_leave_ledger_entry(allocation, -days, valid_from)
	if flt(doc.expired_leaves):
		allocation = frappe.get_doc("Leave Allocation", doc.leave_allocation)
		create_additional_leave_ledger_entry(allocation, flt(doc.expired_leaves), add_days(doc.expires_on, 1))
		doc.db_set("expired_leaves", 0)
	expire_unused(doc.employee)


# --- the allocation --------------------------------------------------------------------------------


def get_carrier_allocation(doc, days: float):
	"""The employee's running Cuti Pengganti allocation, created with the request's days on their
	first approved request."""
	current = frappe.get_all(
		"Leave Allocation",
		filters={
			"employee": doc.employee,
			"leave_type": doc.leave_type,
			"docstatus": 1,
			"to_date": (">=", getdate(doc.work_from_date)),
		},
		pluck="name",
		order_by="from_date",
		limit=1,
	)
	if current:
		return frappe.get_doc("Leave Allocation", current[0])

	allocation = frappe.get_doc(
		{
			"doctype": "Leave Allocation",
			"employee": doc.employee,
			"employee_name": doc.employee_name,
			"leave_type": doc.leave_type,
			"from_date": getdate(doc.work_from_date),
			"to_date": add_days(add_years(getdate(doc.work_from_date), CARRIER_YEARS), -1),
			"new_leaves_allocated": days,
			"description": _("Cuti Pengganti: days off for overtime. Each request's days expire on their own."),
		}
	)
	allocation.flags.ignore_permissions = True
	allocation.insert()
	allocation.submit()
	allocation.flags.created_for_request = True
	return allocation


def credit_from(doc, allocation):
	return max(getdate(doc.work_from_date), getdate(allocation.from_date))


def get_credits(employee: str, leave_type: str) -> list[frappe._dict]:
	rows = frappe.get_all(
		"Compensatory Leave Request",
		filters={
			"employee": employee,
			"leave_type": leave_type,
			"docstatus": 1,
			"status": "Approved",
			"leave_allocation": ("is", "set"),
		},
		fields=[
			"name",
			"work_from_date",
			"work_end_date",
			"half_day",
			"expires_on",
			"expired_leaves",
			"leave_allocation",
			"reason",
		],
		order_by="expires_on, work_from_date",
	)
	for row in rows:
		row.days = request_days(row)
		row.left = row.days
		row.expires_on = getdate(row.expires_on or expiry_for(row.work_from_date))
	return rows


def get_taken(employee: str, leave_type: str, exclude: str | None = None) -> list[frappe._dict]:
	filters = {"employee": employee, "leave_type": leave_type, "docstatus": 1, "status": "Approved"}
	if exclude:
		filters["name"] = ("!=", exclude)
	return frappe.get_all(
		"Leave Application",
		filters=filters,
		fields=["name", "from_date", "total_leave_days"],
		order_by="from_date, creation",
	)


def match_taken_to_credits(credits: list, taken: list) -> float:
	"""Uses the days that expire first for each leave, in date order; returns the days not covered."""
	short = 0.0
	for leave in sorted(taken, key=lambda row: getdate(row.from_date)):
		need = flt(leave.total_leave_days)
		date = getdate(leave.from_date)
		for credit in credits:
			if need <= 0:
				break
			if credit.left <= 0 or not (getdate(credit.work_from_date) <= date <= credit.expires_on):
				continue
			used = min(credit.left, need)
			credit.left -= used
			need -= used
		short += max(need, 0)
	return short


def expire_unused(employee: str) -> None:
	"""Takes what is left of the employee's expired requests off their allocation (or puts it back
	when leave taken from it is cancelled)."""
	leave_type = get_leave_type()
	if not leave_type:
		return
	credits = get_credits(employee, leave_type)
	match_taken_to_credits(credits, get_taken(employee, leave_type))
	date = getdate(today())
	for credit in credits:
		expired = credit.left if credit.expires_on < date else 0
		change = flt(expired) - flt(credit.expired_leaves)
		if not change:
			continue
		allocation = frappe.get_doc("Leave Allocation", credit.leave_allocation)
		create_additional_leave_ledger_entry(allocation, -change, add_days(credit.expires_on, 1))
		frappe.db.set_value("Compensatory Leave Request", credit.name, "expired_leaves", expired)


def process_expired() -> None:
	"""Daily: expire what is left of requests past their date."""
	leave_type = get_leave_type()
	if not leave_type:
		return
	employees = frappe.get_all(
		"Compensatory Leave Request",
		filters={
			"leave_type": leave_type,
			"docstatus": 1,
			"status": "Approved",
			"expires_on": ("<", getdate(today())),
		},
		pluck="employee",
		distinct=True,
	)
	for employee in employees:
		expire_unused(employee)


# --- leave taken ------------------------------------------------------------------------------------


def validate_leave(doc, method=None) -> None:
	"""Leave Application validate: Cuti Pengganti leave must fit days that haven't expired by then."""
	if doc.docstatus != 0 or doc.status in ("Rejected", "Cancelled") or not is_cuti_pengganti(doc.leave_type):
		return
	credits = get_credits(doc.employee, doc.leave_type)
	taken = get_taken(doc.employee, doc.leave_type, exclude=None if doc.is_new() else doc.name)
	short_before = match_taken_to_credits([frappe._dict(c) for c in credits], taken)
	this = frappe._dict(name=doc.name, from_date=doc.from_date, total_leave_days=doc.total_leave_days)
	short_after = match_taken_to_credits([frappe._dict(c) for c in credits], [*taken, this])
	if short_after > short_before:
		frappe.throw(
			_(
				"Not enough Cuti Pengganti for {0}. Each day off can be used until {1} months after the day you worked; check your days on the Leaves page."
			).format(format_date(doc.from_date), get_settings()[1]),
			title=_("Cuti Pengganti"),
			exc=CutiPenggantiError,
		)


def on_leave_change(doc, method=None) -> None:
	"""Leave Application on_submit / on_cancel."""
	if is_cuti_pengganti(doc.leave_type):
		expire_unused(doc.employee)


# --- the employee app -------------------------------------------------------------------------------


def get_summary(employee: str) -> dict:
	"""The employee's requests with what is left of each and when it expires."""
	leave_type, months = get_settings()
	if not leave_type:
		return {"enabled": False}

	credits = get_credits(employee, leave_type)
	match_taken_to_credits(credits, get_taken(employee, leave_type))
	date = getdate(today())
	left_by_name = {c.name: (0 if c.expires_on < date else c.left) for c in credits}

	requests = frappe.get_all(
		"Compensatory Leave Request",
		filters={"employee": employee, "leave_type": leave_type, "docstatus": ("<", 2)},
		fields=[
			"name",
			"work_from_date",
			"work_end_date",
			"half_day",
			"status",
			"docstatus",
			"expires_on",
			"expired_leaves",
			"reason",
		],
		order_by="work_from_date desc",
		limit=50,
	)
	for row in requests:
		row.days = request_days(row)
		row.left = left_by_name.get(row.name)
		row.expired = bool(row.status == "Approved" and row.expires_on and getdate(row.expires_on) < date)

	usable = [c for c in credits if c.left > 0 and c.expires_on >= date]
	next_expiry = None
	if usable:
		first = min(c.expires_on for c in usable)
		next_expiry = {"date": first, "days": sum(c.left for c in usable if c.expires_on == first)}
	return {
		"enabled": True,
		"leave_type": leave_type,
		"months": months,
		"available": sum(c.left for c in usable),
		"next_expiry": next_expiry,
		"requests": requests,
	}


def get_requests_waiting_for(user: str) -> list[dict]:
	"""Open requests waiting for the user's decision (Regular supervisors decide as one group)."""
	leave_type = get_leave_type()
	if not leave_type:
		return []
	rows = frappe.get_all(
		"Leave Application Approver",
		filters={"parenttype": "Compensatory Leave Request", "approver": user, "decision": "Pending"},
		fields=["parent", "approval_level"],
	)
	if not rows:
		return []
	parents = list({row.parent for row in rows})
	decided_by_regular = set(
		frappe.get_all(
			"Leave Application Approver",
			filters={
				"parenttype": "Compensatory Leave Request",
				"parent": ("in", parents),
				"approval_level": ("!=", "Required"),
				"decision": ("!=", "Pending"),
			},
			pluck="parent",
		)
	)
	waiting = {
		row.parent
		for row in rows
		if row.approval_level == "Required" or row.parent not in decided_by_regular
	}
	requests = frappe.get_all(
		"Compensatory Leave Request",
		filters={"name": ("in", list(waiting) or [""]), "docstatus": 0, "status": "Open"},
		fields=["name", "employee", "employee_name", "department", "work_from_date", "work_end_date", "half_day", "reason", "expires_on"],
		order_by="work_from_date",
	)
	for row in requests:
		row.days = request_days(row)
	return requests

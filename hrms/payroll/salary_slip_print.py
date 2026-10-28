# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Data for the one-page "Drea Salary Slip" print format.

Earnings are shown at their full amount, and the pay lost to absent days and leave without
pay is shown as a deduction instead, so the slip reads as earnings - deductions = net pay.
Company-paid BPJS (the slip's Employer Contributions) is listed under both Earnings and
Deductions, so it shows without changing net pay. Tax (e.g. PPh 21) is a deduction component.
Components at 0 are listed with the amount left blank.
"""

import frappe
from frappe import _
from frappe.utils import flt, formatdate


def get_salary_slip_print_data(doc) -> dict:
	earnings, lost = [], 0.0
	for row in counted(doc.earnings):
		amount = flt(row.amount)
		if row.depends_on_payment_days:
			full = flt(row.default_amount) + flt(row.additional_amount)
			if full > amount:
				lost += full - amount
				amount = full
		earnings.append(line(row.salary_component, amount))

	contributions = [line(row.salary_component, row.amount) for row in counted(doc.get("employer_contributions"))]
	earnings += contributions

	deductions = list(contributions)
	attendance = attendance_deductions(doc, flt(lost, 0))
	for row in counted(doc.deductions):
		if "late_entry_days" in (row.formula or ""):
			attendance[0]["amount"] += flt(row.amount)
			continue
		deductions.append(line(row.salary_component, row.amount))
	if flt(doc.get("total_loan_repayment")):
		deductions.append(line(_("Loan Repayment"), doc.total_loan_repayment))
	deductions += attendance

	rounded = not frappe.db.get_single_value("Payroll Settings", "disable_rounded_total")
	return {
		"company": get_company_info(doc.company),
		"period": formatdate(doc.posting_date, "MMMM yyyy"),
		"department": strip_abbr(doc.department, doc.company),
		"earnings": earnings,
		"deductions": deductions,
		"total_earnings": sum(r["amount"] for r in earnings),
		"total_deductions": sum(r["amount"] for r in deductions),
		"net_pay": flt(doc.rounded_total if rounded and doc.rounded_total else doc.net_pay),
	}


def line(component, amount) -> dict:
	return {"label": _(component), "detail": "", "amount": flt(amount), "blank_if_zero": True}


def counted(rows):
	return [row for row in rows or [] if not row.statistical_component and not row.do_not_include_in_total]


def attendance_deductions(doc, lost) -> list[dict]:
	"""Late days, absent days and unpaid leave, in that order, always shown with an amount.

	In whole rupiah, rounded so the rows add up to the pay lost."""
	absent, lwp = flt(doc.absent_days), flt(doc.leave_without_pay)
	# days off the pay for any reason, e.g. joining mid-period, not only absence and unpaid leave
	days_off = max(flt(doc.total_working_days) - flt(doc.payment_days), absent + lwp)
	per_day = lost / days_off if days_off else 0
	absent_amount = flt(per_day * absent, 0)
	lwp_amount = flt(per_day * (absent + lwp), 0) - absent_amount
	rows = [
		{"label": _("Late Days"), "detail": days(doc.late_entry_days), "amount": 0.0},
		{"label": _("Absent Days"), "detail": days(absent), "amount": absent_amount},
		{"label": _("Unpaid Leave"), "detail": days(lwp), "amount": lwp_amount},
	]
	other = lost - absent_amount - lwp_amount
	if other > 0:
		rows.append(
			{
				"label": _("Days Not Paid"),
				"detail": _("before joining or after leaving"),
				"amount": other,
			}
		)
	return rows


def days(value) -> str:
	value = flt(value)
	shown = int(value) if value == int(value) else value
	return _("{0} day").format(shown) if value == 1 else _("{0} days").format(shown)


def strip_abbr(name, company):
	abbr = frappe.get_cached_value("Company", company, "abbr") if company else None
	if name and abbr and name.endswith(f" - {abbr}"):
		return name[: -len(abbr) - 3]
	return name


DEFAULT_LOGO = "/assets/hrms/images/drea-hris-logo.png"


def get_company_info(company) -> dict:
	"""Every CV's slip carries the group's name, logo, address and contacts (Dreambox)."""
	if not company or not frappe.db.exists("Company", company):
		return {"name": company, "logo": DEFAULT_LOGO}
	group = get_group_company(company)
	c = frappe.get_cached_doc("Company", group)
	address = get_company_address(group) or get_company_address(company)
	lines = []
	if address:
		state = address.state if address.state != address.city else None
		lines = [address.address_line1, address.address_line2, address.city]
		lines.append(" ".join(filter(None, [state, address.pincode])))
	return {
		"name": c.company_name,
		"logo": c.company_logo or DEFAULT_LOGO,
		"address": [line for line in lines if line],
		"phone": (address and address.phone) or c.phone_no,
		"email": (address and address.email_id) or c.email,
		"website": c.website,
	}


def get_group_company(company):
	"""The top of the company tree, e.g. Dreambox for CV Dreambox Denalo International."""
	seen = {company}
	while parent := frappe.get_cached_value("Company", company, "parent_company"):
		if parent in seen:
			break
		seen.add(parent)
		company = parent
	return company


def get_company_address(company):
	links = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Company", "link_name": company, "parenttype": "Address"},
		pluck="parent",
	)
	if not links:
		return None
	name = frappe.db.get_value(
		"Address",
		{"name": ["in", links], "disabled": 0},
		"name",
		order_by="is_your_company_address desc, is_primary_address desc",
	)
	return frappe.get_cached_doc("Address", name) if name else None

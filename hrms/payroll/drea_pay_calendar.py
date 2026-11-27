# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""The pay calendar (owner, 27 Nov 2026): a month's pay covers the 19th to the 18th (HR recaps
attendance and unpaid leave on the 19th) and is paid on the 27th.

HR Settings > Pay Period Starts On Day and Pay Day. The start day is the one the employee app's
late days and unpaid days already count by (hrms.hr.penalties). With 1 and 0, the default, monthly
payroll keeps Frappe's calendar month. Only monthly payroll follows it.

The month a pay period belongs to is the month it ends in (19 Oct - 18 Nov is November's pay,
paid 27 Nov): Drea Finance's month and PPh 21's tax month both use the end date.
"""

import datetime

import frappe
from frappe.utils import add_days, add_months, cint, getdate


def settings() -> tuple[int, int]:
	"""(start day, pay day); (1, 0) when not set."""
	meta = frappe.get_meta("HR Settings")
	start_day = pay_day = 0
	if meta.has_field("pay_period_start_day"):
		start_day = cint(frappe.db.get_single_value("HR Settings", "pay_period_start_day"))
	if meta.has_field("pay_day"):
		pay_day = cint(frappe.db.get_single_value("HR Settings", "pay_day"))
	start_day = start_day if 1 <= start_day <= 28 else 1
	pay_day = pay_day if 1 <= pay_day <= 28 else 0
	return start_day, pay_day


def is_on() -> bool:
	return settings() != (1, 0)


def period_containing(date, start_day: int) -> frappe._dict:
	"""The pay period that the date falls in."""
	date = getdate(date)
	month_start = date if date.day >= start_day else add_months(date, -1)
	start = month_start.replace(day=start_day)
	return frappe._dict(start_date=start, end_date=add_days(add_months(start, 1), -1))


def pay_date_of(end_date, pay_day: int) -> datetime.date:
	"""The first pay day on or after the period's last day."""
	end_date = getdate(end_date)
	if not pay_day:
		return end_date
	if pay_day >= end_date.day:
		return end_date.replace(day=pay_day)
	return add_months(end_date, 1).replace(day=pay_day)


def period(date, to_pay: bool = False) -> frappe._dict | None:
	"""The monthly pay period for a date, None when the calendar is not set (Frappe's own month).

	to_pay: the date is a posting date or today, so the answer is the period to be paid next:
	the one whose pay day is the first on or after the date (on 25 Nov: 19 Oct - 18 Nov, paid
	27 Nov; on 28 Nov: 19 Nov - 18 Dec). Without it, the period the date falls in.
	Also gives the period's pay_date."""
	start_day, pay_day = settings()
	if (start_day, pay_day) == (1, 0):
		return None
	date = getdate(date)
	found = period_containing(date, start_day)
	if to_pay and pay_day:
		before = period_containing(add_days(found.start_date, -1), start_day)
		if pay_date_of(before.end_date, pay_day) >= date:
			found = before
	found.pay_date = pay_date_of(found.end_date, pay_day)
	return found

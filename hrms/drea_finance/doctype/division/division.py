# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Division: Drea Finance's divisions, the list payroll totals are sent per (Drea Finance module).

Finance books project cost per division. Drea Finance Settings maps each HR Department to one
(Departments -> Divisions); HR's own Department form knows nothing of it (owner, 25 Nov 2026).
The code (DV-00001 ...) is the record name and never changes; ``SHARED`` is the support-staff
division whose pay is booked to the company itself.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document

CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9-]{1,19}$")
SERIES_PREFIX = "DV-"
SHARED_CODE = "SHARED"


class Division(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		display_order: DF.Int
		division_code: DF.Data | None
		division_name: DF.Data
		is_active: DF.Check
	# end: auto-generated types

	def autoname(self):
		code = (self.division_code or "").strip().upper()
		if not code:
			code = next_division_code()
		elif not CODE_PATTERN.match(code):
			frappe.throw(
				_(
					"Division Code {0} is not valid. Use DV-00001 style codes from Drea Finance, or SHARED."
				).format(frappe.bold(code))
			)
		self.division_code = code
		self.name = code

	def validate(self):
		self.division_name = (self.division_name or "").strip()
		if not self.is_new():
			stored = frappe.db.get_value("Division", self.name, "division_code")
			if stored and self.division_code != stored:
				frappe.throw(_("Division Code cannot be changed once set."))
			if not self.is_active and frappe.db.get_value("Division", self.name, "is_active"):
				self.refuse_deactivation_if_in_use()

	def refuse_deactivation_if_in_use(self):
		"""Finance rule A30/A32: master data is add-and-deactivate, and a row in use refuses deactivation."""
		departments = frappe.get_all(
			"Drea Finance Department", filters={"division": self.name}, pluck="department", limit=5
		)
		if departments:
			frappe.throw(
				_("Division {0} is still mapped to: {1}. Change the mapping in Drea Finance Settings first.").format(
					frappe.bold(self.name), ", ".join(departments)
				),
				title=_("Division In Use"),
			)


def next_division_code() -> str:
	"""The next free DV- number. Existing codes come from Drea Finance and are imported as they are,
	so the series is read from the table rather than from a counter."""
	highest = 0
	for name in frappe.get_all("Division", filters={"name": ["like", f"{SERIES_PREFIX}%"]}, pluck="name"):
		suffix = name[len(SERIES_PREFIX) :]
		if suffix.isdigit():
			highest = max(highest, int(suffix))
	return f"{SERIES_PREFIX}{highest + 1:05d}"


def get_active_divisions() -> list[dict]:
	return frappe.get_all(
		"Division",
		filters={"is_active": 1},
		fields=["name", "division_name", "display_order"],
		order_by="display_order asc, name asc",
	)

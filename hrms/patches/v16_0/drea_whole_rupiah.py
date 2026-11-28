# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Money in whole rupiah (owner, 25 Nov 2026; Drea Design System: "Rp 1.234.567", no decimals).

Frappe has no display-only switch for decimals: the currency precision also decides how money
fields are rounded when saved. So from now on money amounts are kept in whole rupiah, which is
how Indonesian payslips, BPJS and PPh 21 are paid. Amounts saved before stay as they are.

- System Settings: Currency Precision 0 (rounding and printing on the server)
- Currency IDR: number format "#.###", and System Settings uses the currency's format, so the
  desk shows "Rp 1.234.567" while other numbers keep a decimal comma ("11,5")
"""

import frappe


def execute():
	if frappe.db.exists("Currency", "IDR"):
		frappe.db.set_value("Currency", "IDR", "number_format", "#.###")

	settings = frappe.get_single("System Settings")
	settings.currency_precision = "0"
	settings.use_number_format_from_currency = 1
	# on_update copies these into the defaults the desk reads at login
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)
	frappe.clear_cache()

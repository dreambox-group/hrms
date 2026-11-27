# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""PPh 21 on Drea salary slips (owner, 27 Nov 2026): a first version for Finance and the tax
consultant to check. It only runs when Payroll Settings > Calculate PPh 21 is ticked, and only on
slips whose salary structure has the PPh21 component (full-time staff and interns).

The company pays PPh 21 (owner, 27 Nov 2026): the pay HR enters is what the person receives. So
PPh21 is a company-paid line on the slip (employer contributions: shown, never taken from pay;
Drea Finance PPH21_COMPANY). It is not grossed up: tax the company bears is not the employee's
income, so it is not added to the gross it is worked out on.

The rules (PP 58/2023, PMK 168/2023):

- January to November: TER. The month's gross times the rate of the person's TER category, which
  follows their PTKP status. Gross = taxable earnings, less taxable cuts (unpaid days, late
  penalty), plus the BPJS the company pays that counts as income (Kesehatan 4%, JKK, JKM). THR or
  an incentive paid in a month is part of that month's gross.
- The year's last month (December, or the month the person leaves): the year's tax in full,
  Pasal 17 rates on the year's net income above PTKP, less what TER took earlier in the year.
  Net income = the year's gross, less job costs (5%, at most Rp500,000 for each month paid),
  less the employee's own JHT and JP.
- The tax month is the month the pay period ends in, which is the month it is paid
  (hrms.payroll.drea_pay_calendar).

Left to the tax consultant: getting back what was paid too much when the year's tax comes out
below what TER took (the slip shows the amount, PPh 21 is 0 that month), gross-up if wanted, the 20% more for someone without NPWP, and
annualising for someone who leaves Indonesia. Each slip shows its sum in "PPh 21 Working".
"""

from decimal import ROUND_DOWN, Decimal

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

PPH21 = "PPh21"
# the employee's own pension contributions, taken off the year's income in the last month
PENSION = ("BPJS JHT Karyawan", "BPJS JP Karyawan")

PTKP = {
	"TK/0": 54_000_000,
	"TK/1": 58_500_000,
	"TK/2": 63_000_000,
	"TK/3": 67_500_000,
	"K/0": 58_500_000,
	"K/1": 63_000_000,
	"K/2": 67_500_000,
	"K/3": 72_000_000,
}
PTKP_OPTIONS = "\n" + "\n".join(PTKP)
CATEGORY = {
	"TK/0": "A",
	"TK/1": "A",
	"K/0": "A",
	"TK/2": "B",
	"TK/3": "B",
	"K/1": "B",
	"K/2": "B",
	"K/3": "C",
}

# Monthly TER (PP 58/2023, lampiran): (highest monthly gross, rate %). Above the last row: 34%.
TER = {
	"A": (
		(5_400_000, 0), (5_650_000, 0.25), (5_950_000, 0.5), (6_300_000, 0.75), (6_750_000, 1),
		(7_500_000, 1.25), (8_550_000, 1.5), (9_650_000, 1.75), (10_050_000, 2), (10_350_000, 2.25),
		(10_700_000, 2.5), (11_050_000, 3), (11_600_000, 3.5), (12_500_000, 4), (13_750_000, 5),
		(15_100_000, 6), (16_950_000, 7), (19_750_000, 8), (24_150_000, 9), (26_450_000, 10),
		(28_000_000, 11), (30_050_000, 12), (32_400_000, 13), (35_400_000, 14), (39_100_000, 15),
		(43_850_000, 16), (47_800_000, 17), (51_400_000, 18), (56_300_000, 19), (62_200_000, 20),
		(68_600_000, 21), (77_500_000, 22), (89_000_000, 23), (103_000_000, 24), (125_000_000, 25),
		(157_000_000, 26), (206_000_000, 27), (337_000_000, 28), (454_000_000, 29), (550_000_000, 30),
		(695_000_000, 31), (910_000_000, 32), (1_400_000_000, 33),
	),
	"B": (
		(6_200_000, 0), (6_500_000, 0.25), (6_850_000, 0.5), (7_300_000, 0.75), (9_200_000, 1),
		(10_750_000, 1.5), (11_250_000, 2), (11_600_000, 2.5), (12_600_000, 3), (13_600_000, 4),
		(14_950_000, 5), (16_400_000, 6), (18_450_000, 7), (21_850_000, 8), (26_000_000, 9),
		(27_700_000, 10), (29_350_000, 11), (31_450_000, 12), (33_950_000, 13), (37_100_000, 14),
		(41_100_000, 15), (45_800_000, 16), (49_500_000, 17), (53_800_000, 18), (58_500_000, 19),
		(64_000_000, 20), (71_000_000, 21), (80_000_000, 22), (93_000_000, 23), (109_000_000, 24),
		(129_000_000, 25), (163_000_000, 26), (211_000_000, 27), (374_000_000, 28), (459_000_000, 29),
		(555_000_000, 30), (704_000_000, 31), (957_000_000, 32), (1_405_000_000, 33),
	),
	"C": (
		(6_600_000, 0), (6_950_000, 0.25), (7_350_000, 0.5), (7_800_000, 0.75), (8_850_000, 1),
		(9_800_000, 1.25), (10_950_000, 1.5), (11_200_000, 1.75), (12_050_000, 2), (12_950_000, 3),
		(14_150_000, 4), (15_550_000, 5), (17_050_000, 6), (19_500_000, 7), (22_700_000, 8),
		(26_600_000, 9), (28_100_000, 10), (30_100_000, 11), (32_600_000, 12), (35_400_000, 13),
		(38_900_000, 14), (43_000_000, 15), (47_400_000, 16), (51_200_000, 17), (55_800_000, 18),
		(60_400_000, 19), (66_700_000, 20), (74_500_000, 21), (83_200_000, 22), (95_600_000, 23),
		(110_000_000, 24), (134_000_000, 25), (169_000_000, 26), (221_000_000, 27), (390_000_000, 28),
		(463_000_000, 29), (561_000_000, 30), (709_000_000, 31), (965_000_000, 32), (1_419_000_000, 33),
	),
}  # fmt: skip
TER_TOP_RATE = 34

# Pasal 17 (UU HPP): (top of the band, rate %); the last band has no top
PASAL_17 = ((60_000_000, 5), (250_000_000, 15), (500_000_000, 25), (5_000_000_000, 30), (None, 35))
JOB_COST_RATE = Decimal("0.05")
JOB_COST_MONTHLY_CAP = 500_000


# --- the sums -----------------------------------------------------------------------------------


def ter_rate(category: str, gross) -> float:
	for top, rate in TER[category]:
		if flt(gross) <= top:
			return rate
	return TER_TOP_RATE


def ter_tax(category: str, gross) -> int:
	"""The month's PPh 21 under TER, in whole rupiah (rounded down)."""
	return rupiah(Decimal(str(flt(gross))) * Decimal(str(ter_rate(category, gross))) / 100)


def pasal_17(taxable) -> int:
	tax, bottom = Decimal(0), 0
	for top, rate in PASAL_17:
		if taxable <= bottom:
			break
		band = (min(taxable, top) if top else taxable) - bottom
		tax += Decimal(band) * rate / 100
		bottom = top
	return rupiah(tax)


def year_tax(gross, pension, months: int, ptkp: int) -> frappe._dict:
	"""The year's PPh 21 in its last month."""
	gross = Decimal(str(flt(gross)))
	job_cost = min(rupiah(gross * JOB_COST_RATE), JOB_COST_MONTHLY_CAP * months)
	net = gross - job_cost - Decimal(str(flt(pension)))
	taxable = max(0, int((net - ptkp) // 1000) * 1000)  # rounded down to the thousand
	return frappe._dict(job_cost=job_cost, net=rupiah(net), taxable=taxable, tax=pasal_17(taxable))


def rupiah(value) -> int:
	return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_DOWN))


def idr(value) -> str:
	return "Rp " + f"{int(value):,}".replace(",", ".")


# --- on a salary slip -----------------------------------------------------------------------------


def is_on() -> bool:
	return frappe.get_meta("Payroll Settings").has_field("calculate_pph21") and bool(
		cint(frappe.db.get_single_value("Payroll Settings", "calculate_pph21"))
	)


def structure_has_pph21(structure: str) -> bool:
	return bool(
		frappe.db.exists(
			"Salary Detail",
			{"parenttype": "Salary Structure", "parent": structure, "salary_component": PPH21},
		)
	)


def taxable(component: str) -> bool:
	return bool(cint(frappe.get_cached_value("Salary Component", component, "is_tax_applicable")))


def month_gross(rows) -> float:
	"""rows: (parentfield, salary_component, amount). Taxable earnings and company-paid BPJS that
	counts as income, less taxable cuts."""
	total = 0.0
	for parentfield, component, amount in rows:
		if component == PPH21 or not taxable(component):
			continue
		total += -flt(amount) if parentfield == "deductions" else flt(amount)
	return total


def slip_rows(slip):
	return [
		(table, row.salary_component, row.amount)
		for table in ("earnings", "deductions", "employer_contributions")
		for row in slip.get(table)
	]


def apply(slip):
	"""Salary Slip.calculate_net_pay, once every other component is worked out."""
	if not slip.salary_structure or not is_on() or not structure_has_pph21(slip.salary_structure):
		return
	status = frappe.db.get_value("Employee", slip.employee, "ptkp_status")
	if status not in PTKP:
		frappe.throw(
			_(
				"Set the PTKP Status of {0} ({1}) on their Employee record so PPh 21 can be worked out, "
				"or untick Calculate PPh 21 in Payroll Settings."
			).format(slip.employee_name or slip.employee, slip.employee),
			title=_("PTKP Status missing"),
		)

	rows = slip_rows(slip)
	gross = month_gross(rows)
	end = getdate(slip.end_date)
	leaves = slip.relieving_date and getdate(slip.relieving_date) <= end
	if end.month == 12 or leaves:
		amount, working = last_month(slip, status, rows, gross, end)
	else:
		category = CATEGORY[status]
		amount = ter_tax(category, gross)
		working = _("TER {0} ({1}): {2}% of {3} gross = {4}").format(
			category, status, ter_rate(category, gross), idr(gross), idr(amount)
		)

	set_amount(slip, amount)
	if slip.meta.has_field("pph21_working"):
		slip.pph21_working = working


def last_month(slip, status, rows, gross, end):
	earlier = frappe.get_all(
		"Salary Slip",
		filters={
			"employee": slip.employee,
			"docstatus": 1,
			"name": ("!=", slip.name or ""),
			"end_date": ("between", [end.replace(month=1, day=1), slip.start_date]),
		},
		fields=["name", "end_date"],
	)
	earlier = [s for s in earlier if getdate(s.end_date) < getdate(slip.start_date)]
	earlier_rows = (
		frappe.get_all(
			"Salary Detail",
			filters={"parenttype": "Salary Slip", "parent": ("in", [s.name for s in earlier])},
			fields=["parentfield", "salary_component", "amount"],
			as_list=True,
		)
		if earlier
		else []
	)
	all_rows = list(earlier_rows) + rows
	year_gross = month_gross(earlier_rows) + gross
	pension = sum(flt(a) for t, c, a in all_rows if t == "deductions" and c in PENSION)
	withheld = sum(flt(a) for t, c, a in earlier_rows if c == PPH21)
	months = len({(getdate(s.end_date).year, getdate(s.end_date).month) for s in earlier}) + 1
	year = year_tax(year_gross, pension, months, PTKP[status])

	amount = rupiah(year.tax - withheld)
	working = _(
		"Year's last month ({0} months): gross {1}, less job costs {2} and JHT/JP {3} = net {4}; "
		"less PTKP {5} {6} = taxable {7}; tax for the year {8}; paid under TER earlier {9}"
	).format(
		months,
		idr(year_gross),
		idr(year.job_cost),
		idr(pension),
		idr(year.net),
		status,
		idr(PTKP[status]),
		idr(year.taxable),
		idr(year.tax),
		idr(withheld),
	)
	if amount < 0:
		working += _("; {0} too much was paid this year: the tax consultant claims it back").format(
			idr(-amount)
		)
		amount = 0
	return amount, working + _("; PPh 21 this month {0}").format(idr(amount))


def set_amount(slip, amount):
	component = frappe.get_cached_doc("Salary Component", PPH21)
	data = frappe._dict(
		salary_component=PPH21,
		abbr=component.salary_component_abbr,
		depends_on_payment_days=0,
		is_tax_applicable=0,
		do_not_include_in_total=0,
		do_not_include_in_accounts=0,
		variable_based_on_taxable_salary=0,
		exempted_from_income_tax=0,
	)
	slip.update_component_row(data, amount, "employer_contributions", remove_if_zero_valued=1)

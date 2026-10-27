# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import format_date

# Wether to proceed with frequency change
PROCEED_WITH_FREQUENCY_CHANGE = False


class HRSettings(Document):
	def validate(self):
		self.set_naming_series()
		from hrms.hr.doctype.leave_application.leave_fixed_length import validate_settings

		validate_settings(self)
		if not 0 <= (self.pay_period_start_day or 0) <= 28:
			frappe.throw(_("The pay period can start on day 1 to 28 of the month."))

		# Based on proceed flag
		global PROCEED_WITH_FREQUENCY_CHANGE
		if not PROCEED_WITH_FREQUENCY_CHANGE:
			self.validate_frequency_change()
		PROCEED_WITH_FREQUENCY_CHANGE = False

	def on_update(self):
		self.start_leave_counting_for_added_types()
		if self.leave_google_calendar and self.has_value_changed("leave_google_calendar"):
			# upcoming approved leave goes onto the new calendar
			frappe.enqueue(
				"hrms.hr.doctype.leave_application.leave_calendar.push_missing_leave_to_google_calendar",
				queue="long",
				enqueue_after_commit=True,
			)

	def start_leave_counting_for_added_types(self):
		"""Types just added to "Employee Types without Leave Allocation": their employees' leave
		pushes the end date from today on (earlier leave isn't counted twice)."""
		from hrms.hr.doctype.leave_application.leave_end_date import start_counting_for_types

		before = self.get_doc_before_save()
		old = (
			{row.employment_type for row in (before.get("employment_types_without_leave_allocation") or [])}
			if before
			else set()
		)
		new = {row.employment_type for row in (self.get("employment_types_without_leave_allocation") or [])}
		start_counting_for_types(new - old)

	def set_naming_series(self):
		from erpnext.utilities.naming import set_by_naming_series

		set_by_naming_series(
			"Employee",
			"employee_number",
			self.get("emp_created_by") == "Naming Series",
			hide_name_field=True,
		)

	def validate_frequency_change(self):
		weekly_job, monthly_job = None, None

		try:
			weekly_job = frappe.get_doc(
				"Scheduled Job Type",
				{"method": "hrms.controllers.employee_reminders.send_reminders_in_advance_weekly"},
			)

			monthly_job = frappe.get_doc(
				"Scheduled Job Type",
				{"method": "hrms.controllers.employee_reminders.send_reminders_in_advance_monthly"},
			)
		except frappe.DoesNotExistError:
			return

		next_weekly_trigger = weekly_job.get_next_execution()
		next_monthly_trigger = monthly_job.get_next_execution()

		if self.freq_changed_from_monthly_to_weekly():
			if next_monthly_trigger < next_weekly_trigger:
				self.show_freq_change_warning(next_monthly_trigger, next_weekly_trigger)

		elif self.freq_changed_from_weekly_to_monthly():
			if next_monthly_trigger > next_weekly_trigger:
				self.show_freq_change_warning(next_weekly_trigger, next_monthly_trigger)

	def freq_changed_from_weekly_to_monthly(self):
		return self.has_value_changed("frequency") and self.frequency == "Monthly"

	def freq_changed_from_monthly_to_weekly(self):
		return self.has_value_changed("frequency") and self.frequency == "Weekly"

	def show_freq_change_warning(self, from_date, to_date):
		from_date = frappe.bold(format_date(from_date))
		to_date = frappe.bold(format_date(to_date))

		raise_exception = frappe.ValidationError
		if (
			frappe.flags.in_test
			or frappe.flags.in_patch
			or frappe.flags.in_install
			or frappe.flags.in_migrate
		):
			raise_exception = False

		frappe.msgprint(
			msg=frappe._(
				"Employees will miss holiday reminders from {} until {}. <br> Do you want to proceed with this change?"
			).format(from_date, to_date),
			title="Confirm change in Frequency",
			primary_action={
				"label": frappe._("Yes, Proceed"),
				"client_action": "hrms.proceed_save_with_reminders_frequency_change",
			},
			raise_exception=raise_exception,
		)


@frappe.whitelist()
def set_proceed_with_frequency_change():
	"""Enables proceed with frequency change"""
	global PROCEED_WITH_FREQUENCY_CHANGE
	PROCEED_WITH_FREQUENCY_CHANGE = True

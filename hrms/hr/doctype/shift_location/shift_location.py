# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from hrms.hr.utils import set_geolocation_from_coordinates

# HR: an office check-in counts within 500 m of the office at most
MAX_CHECKIN_RADIUS = 500


class ShiftLocation(Document):
	def validate(self):
		self.set_geolocation()
		if cint(self.checkin_radius) > MAX_CHECKIN_RADIUS:
			frappe.throw(
				_("The check-in radius can be at most {0} meters.").format(MAX_CHECKIN_RADIUS),
				title=_("Radius Too Large"),
			)

	@frappe.whitelist()
	def set_geolocation(self):
		set_geolocation_from_coordinates(self)

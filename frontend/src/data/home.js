import { createResource } from "frappe-ui"

// today's notices, leave waiting for the user and, for leave approvers, their team's check-ins
export const homeData = createResource({
	url: "hrms.api.home.get_home_data",
	cache: "hrms:home_data",
})

export const leaveDecision = createResource({
	url: "hrms.hr.doctype.leave_application.leave_application.record_leave_decision",
})

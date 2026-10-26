import { createResource } from "frappe-ui"

// today's notices, leave waiting for the user and, for leave approvers, their team's check-ins
export const homeData = createResource({
	url: "hrms.api.home.get_home_data",
	cache: "hrms:home_data",
})

// one tap: a vote with approval by levels, otherwise the chosen approver's decision
export const leaveDecision = createResource({
	url: "hrms.hr.doctype.leave_application.leave_application.decide_leave_application",
})

export const leaveDocumentUpload = createResource({
	url: "hrms.hr.doctype.leave_application.leave_documents.upload_leave_document",
})

// a supervisor's decision on a Cuti Pengganti request (a day worked, for a day off)
export const cutiPenggantiDecision = createResource({
	url: "hrms.api.employee_app.decide_cuti_pengganti",
})

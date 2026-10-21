import { createResource } from "frappe-ui"

export const settings = createResource({
	url: "hrms.api.get_hr_settings",
	// loaded from main.js once requests are configured: the menu imports this before that point
})
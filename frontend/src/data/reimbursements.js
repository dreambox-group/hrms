import { createResource } from "frappe-ui"

// Reimbursement claims live in Drea Finance; the app sends them and follows their progress there.

// where a claim is now (Drea Finance's progress state) → the badge colour
export const PROGRESS_TONE = {
	waiting: "warn",
	approved: "info",
	paid: "ok",
	stopped: "neutral",
	draft: "neutral",
}

// the newest few, for the Home card
export const latestReimbursements = createResource({
	url: "hrms.api.reimbursements.get_my_reimbursements",
	params: { start: 0, limit: 3 },
})

// a file to this site first (private), so the claim can carry it on to Drea Finance
export async function uploadProof(file) {
	const form = new FormData()
	form.append("file", file, file.name)
	form.append("is_private", "1")
	form.append("folder", "Home")
	const response = await fetch("/api/method/upload_file", {
		method: "POST",
		headers: { "X-Frappe-CSRF-Token": window.csrf_token },
		body: form,
	})
	const body = await response.json().catch(() => ({}))
	if (!response.ok || !body.message?.file_url) {
		throw new Error(body._error_message || "The file could not be uploaded.")
	}
	return body.message.file_url
}

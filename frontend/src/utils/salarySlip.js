import dayjs from "@/utils/dayjs"

// "October 2026" for a calendar month, otherwise the dates (Dreambox pays the 19th to the 18th)
export function slipPeriod(slip) {
	const start = dayjs(slip.start_date)
	const end = dayjs(slip.end_date)
	if (start.date() === 1 && end.isSame(start.endOf("month"), "day")) return start.format("MMMM YYYY")
	return `${start.format("D MMM")} – ${end.format("D MMM YYYY")}`
}

// the server renders the PDF with the slip's print format; the browser saves it
export async function downloadSlipPDF(name) {
	const headers = { "X-Frappe-Site-Name": window.location.hostname }
	if (window.csrf_token) headers["X-Frappe-CSRF-Token"] = window.csrf_token
	const response = await fetch("/api/method/hrms.api._download_pdf", {
		method: "POST",
		headers,
		body: new URLSearchParams({ doctype: "Salary Slip", docname: name }),
	})
	if (!response.ok) throw new Error(response.statusText || "Download failed")
	const url = window.URL.createObjectURL(await response.blob())
	const link = document.createElement("a")
	link.href = url
	link.download = `${name.replaceAll("/", "-")}.pdf`
	link.click()
	setTimeout(() => window.URL.revokeObjectURL(url), 3000)
}

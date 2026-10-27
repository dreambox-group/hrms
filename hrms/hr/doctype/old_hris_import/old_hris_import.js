// Copyright (c) 2026, Dreambox and contributors
// For license information, please see license.txt

const RUNNING = ["Checking", "Importing"];
const LEVELS = {
	error: { label: __("Not imported"), color: "red" },
	warning: { label: __("Imported with a change"), color: "orange" },
	info: { label: __("Note"), color: "blue" },
};

frappe.ui.form.on("Old HRIS Import", {
	onload(frm) {
		if (!frm.is_new()) return;
		frappe.call("hrms.hr.doctype.old_hris_import.old_hris_import.get_defaults").then(({ message }) => {
			for (const [field, value] of Object.entries(message || {})) {
				if (value && !frm.doc[field]) frm.set_value(field, value);
			}
		});
	},

	setup(frm) {
		frappe.realtime.on("old_hris_import_done", ({ name }) => {
			if (name === frm.doc.name) frm.reload_doc();
		});
	},

	refresh(frm) {
		render_report(frm);
		clearTimeout(frm.old_hris_poll);
		if (frm.is_new()) return;

		const running = RUNNING.includes(frm.doc.status);
		frm.toggle_enable(
			["workbook", "attendance_files", "default_company", "import_from", "create_logins", "annual_leave_type", "unpaid_leave_type", "other_leave_type", "mappings"],
			!running
		);
		if (running) {
			frm.dashboard.set_headline(
				frm.doc.status === "Checking"
					? __("Checking the file. Nothing is saved; this can take a few minutes.")
					: __("Importing. This can take a few minutes; you can leave this page."),
				"orange"
			);
			// in case the realtime message is missed
			frm.old_hris_poll = setTimeout(() => frm.reload_doc(), 5000);
			return;
		}

		const needs_check = frm.doc.__onload?.needs_check || frm.is_dirty();
		const checked = ["Checked", "Imported"].includes(frm.doc.status);
		if (checked && needs_check) {
			frm.dashboard.set_headline(
				__("A file, an option or the matching changed since the last check. Check again before importing."),
				"orange"
			);
		} else if (frm.doc.status === "Checked") {
			frm.dashboard.set_headline(
				__("Checked. Read the result below and the matching table, then Import."),
				"blue"
			);
		}

		const check = frm.add_custom_button(checked ? __("Check Again") : __("Check"), () =>
			// saving an unchanged form never resolves
			(frm.is_dirty() ? frm.save() : Promise.resolve()).then(() =>
				frm.call("check").then(() => frm.reload_doc())
			)
		);
		if (checked && !needs_check) {
			frm.add_custom_button(__("Import"), () => confirm_import(frm)).removeClass("btn-default").addClass("btn-primary");
		} else {
			check.removeClass("btn-default").addClass("btn-primary");
		}
	},
});

// whole numbers as they are, half days with one decimal
const count = (n) => (Number.isInteger(n) ? String(n) : format_number(n, null, 1));

function confirm_import(frm) {
	const counts = JSON.parse(frm.doc.report || "{}").counts || {};
	const lines = Object.entries(counts)
		.slice(0, 12)
		.map(([what, n]) => `<li>${frappe.utils.escape_html(what)}: <b>${count(n)}</b></li>`)
		.join("");
	frappe.confirm(
		`<p>${__("The import does what the last check showed:")}</p><ul>${lines}</ul>
		<p>${__("Take a backup first. Running it again later skips what is already imported.")}</p>`,
		() => frm.call("start_import").then(() => frm.reload_doc())
	);
}

function render_report(frm) {
	const wrapper = frm.get_field("result_html").$wrapper;
	if (!frm.doc.report) {
		wrapper.html(`<p class="text-muted">${__("Save, then press Check. Nothing is saved by a check.")}</p>`);
		return;
	}
	const report = JSON.parse(frm.doc.report);
	if (report.failed) {
		wrapper.html(`<div class="alert alert-danger">${__("It stopped with an error. Nothing more was changed after it.")}</div>
			<pre style="white-space: pre-wrap; font-size: 11px">${frappe.utils.escape_html(report.failed)}</pre>`);
		return;
	}

	const title = report.dry_run
		? __("Check from {0}. Nothing was saved; this is what an import would do.", [frappe.datetime.str_to_user(report.finished)])
		: __("Imported on {0}.", [frappe.datetime.str_to_user(report.finished)]);
	const counts = Object.entries(report.counts || {})
		.map(([what, n]) => `<tr><td>${frappe.utils.escape_html(what)}</td><td class="text-right"><b>${count(n)}</b></td></tr>`)
		.join("");
	const order = { error: 0, warning: 1, info: 2 };
	const messages = (report.messages || []).slice().sort((a, b) => order[a[0]] - order[b[0]]);
	const shown = messages.slice(0, 500);
	const rows = shown
		.map(
			([level, sheet, row, text]) => `<tr>
				<td style="white-space: nowrap"><span class="indicator-pill ${LEVELS[level].color}">${LEVELS[level].label}</span></td>
				<td>${frappe.utils.escape_html(sheet)}${row ? ` · ${__("row {0}", [row])}` : ""}</td>
				<td>${frappe.utils.escape_html(text)}</td></tr>`
		)
		.join("");
	const more = messages.length - shown.length + (report.dropped || 0);

	wrapper.html(`
		<p><b>${title}</b></p>
		<p>${__("{0} not imported, {1} imported with a change.", [report.errors || 0, report.warnings || 0])}</p>
		<table class="table table-bordered table-sm" style="max-width: 560px">${counts}</table>
		${
			messages.length
				? `<div class="d-flex align-items-center justify-content-between mt-4 mb-2">
					<b>${__("Rows to look at")}</b>
					<button class="btn btn-xs btn-default download-report">${__("Download as CSV")}</button>
				</div>
				<table class="table table-bordered table-sm"><tbody>${rows}</tbody></table>
				${more > 0 ? `<p class="text-muted">${__("{0} more in the download.", [more])}</p>` : ""}`
				: ""
		}`);
	wrapper.find(".download-report").on("click", () => {
		const data = [["Level", "Sheet", "Row", "Message"], ...messages.map(([l, s, r, t]) => [LEVELS[l].label, s, r, t])];
		frappe.tools.downloadify(data, null, `${frm.doc.name} ${report.dry_run ? "check" : "import"}`);
	});
}

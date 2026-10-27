// Copyright (c) 2026, Dreambox and contributors
// For license information, please see license.txt

frappe.ui.form.on("Leave Change Request", {
	refresh(frm) {
		const isHR = ["HR Manager", "HR User", "System Manager"].some((role) => frappe.user.has_role(role));
		if (frm.is_new() || frm.doc.status !== "Open" || !isHR) return;

		frm.dashboard.set_headline(
			frm.doc.informed_hr
				? __("The employee says they have already told HR about this change.")
				: __("The employee has not confirmed telling HR."),
			frm.doc.informed_hr ? "blue" : "orange"
		);
		frm.add_custom_button(__("Approve"), () => decide(frm, "Approved"))
			.removeClass("btn-default")
			.addClass("btn-primary");
		frm.add_custom_button(__("Reject"), () => decide(frm, "Rejected"));
	},
});

function decide(frm, decision) {
	const what =
		frm.doc.change === "Cancel the leave"
			? __("The leave {0} will be cancelled.", [frm.doc.leave_application])
			: __("The leave {0} will be cancelled and a leave from {1} to {2} made in its place.", [
					frm.doc.leave_application,
					frappe.datetime.str_to_user(frm.doc.new_from_date),
					frappe.datetime.str_to_user(frm.doc.new_to_date),
			  ]);
	const dialog = new frappe.ui.Dialog({
		title: decision === "Approved" ? __("Approve the request") : __("Reject the request"),
		fields: [
			{ fieldtype: "HTML", options: decision === "Approved" ? `<p>${what}</p>` : "" },
			{ fieldname: "note", fieldtype: "Small Text", label: __("Note for the employee (optional)") },
		],
		primary_action_label: decision === "Approved" ? __("Approve") : __("Reject"),
		primary_action({ note }) {
			frm.call("decide", { decision, note }).then(() => {
				dialog.hide();
				frm.reload_doc();
			});
		},
	});
	dialog.show();
}

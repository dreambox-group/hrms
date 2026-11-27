// Copyright (c) 2026, Dreambox and contributors
// For license information, please see license.txt

// Draft THR (hrms.payroll.drea_thr): works out each person's THR and makes draft Additional
// Salaries for HR to check and submit; the payroll run of that month pays them.
frappe.listview_settings["Additional Salary"] = {
	onload(listview) {
		if (!frappe.user.has_role(["HR Manager", "HR User", "System Manager"])) return;
		listview.page.add_inner_button(__("Draft THR"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Draft THR"),
				fields: [
					{
						fieldname: "company",
						fieldtype: "Link",
						options: "Company",
						label: __("Company"),
						reqd: 1,
						default: frappe.defaults.get_user_default("Company"),
					},
					{
						fieldname: "holiday_date",
						fieldtype: "Date",
						label: __("Hari Raya"),
						reqd: 1,
						description: __("Service is counted up to this day."),
					},
					{
						fieldname: "payroll_date",
						fieldtype: "Date",
						label: __("Pay with the payroll of"),
						reqd: 1,
						description: __("A day in the pay period that pays THR, before Hari Raya."),
					},
				],
				primary_action_label: __("Make Drafts"),
				primary_action(values) {
					frappe
						.call({
							method: "hrms.payroll.drea_thr.draft_thr",
							args: values,
							freeze: true,
						})
						.then(({ message }) => {
							dialog.hide();
							const list = (items) =>
								items.length
									? `<ul>${items.map((i) => `<li>${frappe.utils.escape_html(i)}</li>`).join("")}</ul>`
									: `<p>${__("None")}</p>`;
							frappe.msgprint({
								title: __("THR drafts"),
								message:
									`<p><b>${__("Made, as drafts to check and submit")}</b></p>${list(message.made)}` +
									(message.skipped.length
										? `<p><b>${__("Not made")}</b></p>${list(message.skipped)}`
										: ""),
							});
							listview.refresh();
						});
				},
			});
			dialog.show();
		});
	},
};

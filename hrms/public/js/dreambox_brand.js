// Dreambox branding on the desk (owner, 11 Nov 2026): the mark at the top of each module's
// sidebar ("HR Setup ▾", "Payroll ▾", ...) is the Dreambox logo instead of the module's icon.
// Loaded as a plain file (hooks.app_include_js), after the desk bundle defines the header.
(function () {
	const LOGO = "/assets/hrms/images/dreambox-logo.png";
	const Header = frappe.ui && frappe.ui.SidebarHeader;
	if (!Header || Header.prototype.__dreambox) return;
	Header.prototype.get_header_logo = function () {
		return `<img src="${LOGO}" alt="Dreambox" style="width: 20px; height: 20px; object-fit: contain;">`;
	};
	Header.prototype.__dreambox = true;
})();

import { computed } from "vue"

import HomeIcon from "@/components/icons/HomeIcon.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import RosterIcon from "@/components/icons/RosterIcon.vue"

import { settings } from "@/data/settings"

// Expenses and Salary Slips only show when HR Settings turn them on for the employee app
export const showExpenses = computed(() => Boolean(settings.data?.show_expenses_in_employee_app))
export const showSalary = computed(() => Boolean(settings.data?.show_salary_in_employee_app))
// Request Attendance and Request a Shift, likewise
export const showAttendanceRequests = computed(() =>
	Boolean(settings.data?.show_attendance_requests_in_employee_app)
)
// Reimbursement goes to Drea Finance, once HR Settings has its address and key
export const showReimbursements = computed(() => Boolean(settings.data?.show_reimbursements))

// the app's main sections: bottom tabs on phones, a top bar on wide screens
export const useMainSections = (__) =>
	computed(() =>
		[
			{ icon: HomeIcon, title: __("Home"), route: "/home" },
			{ icon: AttendanceIcon, title: __("Attendance"), route: "/dashboard/attendance" },
			{ icon: LeaveIcon, title: __("Leaves"), route: "/dashboard/leaves" },
			// everyone's shifts, for every employee (not only approvers)
			{ icon: RosterIcon, title: __("Employee Schedule"), route: "/schedule" },
			// Frappe's own expense claims, unless claims go to Drea Finance instead
			showExpenses.value && !showReimbursements.value && { icon: ExpenseIcon, title: __("Expenses"), route: "/dashboard/expense-claims" },
			showSalary.value && { icon: SalaryIcon, title: __("Salary"), route: "/dashboard/salary-slips" },
			// last: the least frequent of the employee's goals
			showReimbursements.value && { icon: ExpenseIcon, title: __("Reimburse"), route: "/reimbursements" },
		].filter(Boolean)
	)

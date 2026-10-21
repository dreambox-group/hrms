import HomeIcon from "@/components/icons/HomeIcon.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"

// the app's main sections: bottom tabs on phones, a top bar on wide screens
export const getMainSections = (__) => [
	{ icon: HomeIcon, title: __("Home"), route: "/home" },
	{ icon: AttendanceIcon, title: __("Attendance"), route: "/dashboard/attendance" },
	{ icon: LeaveIcon, title: __("Leaves"), route: "/dashboard/leaves" },
	{ icon: ExpenseIcon, title: __("Expenses"), route: "/dashboard/expense-claims" },
	{ icon: SalaryIcon, title: __("Salary"), route: "/dashboard/salary-slips" },
]

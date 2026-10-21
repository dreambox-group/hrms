<template>
	<BaseLayout wide>
		<template #body>
			<div class="flex flex-col gap-5 p-4 lg:p-8 pb-24 w-full">
				<div>
					<div class="text-sm font-medium text-gray-500">{{ dayjs().format("dddd, D MMMM YYYY") }}</div>
					<h1 class="text-2xl font-semibold text-gray-900 mt-1">
						{{ __("Hello, {0}", [employee?.data?.first_name]) }}
					</h1>
				</div>

				<HomeNotices />

				<div class="flex flex-col lg:flex-row gap-5 items-start">
					<aside class="w-full lg:w-80 flex-none flex flex-col gap-4">
						<div class="rounded-lg border bg-white">
							<CheckInPanel :show-greeting="false" />
						</div>

						<!-- phones: approvals is a button with a red count -->
						<router-link
							v-if="isApprover"
							:to="{ name: 'Approvals' }"
							class="lg:hidden flex flex-row items-center justify-between rounded-lg border bg-white px-4 py-4"
						>
							<span class="flex flex-row items-center gap-3 text-base font-semibold text-gray-900">
								<FeatherIcon name="check-square" class="h-5 w-5 text-gray-500" />
								{{ __("Approvals") }}
							</span>
							<span class="flex flex-row items-center gap-2">
								<span
									v-if="waitingCount"
									class="rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white"
								>
									{{ waitingCount }}
								</span>
								<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
							</span>
						</router-link>

						<div v-if="balances.length" class="rounded-lg border bg-white p-4 flex flex-col gap-2">
							<h3 class="text-base font-semibold text-gray-900">{{ __("My leave balance") }}</h3>
							<div
								v-for="balance in balances"
								:key="balance.type"
								class="flex flex-row justify-between text-sm"
							>
								<span class="text-gray-700">{{ balance.type }}</span>
								<span>
									<span class="font-semibold text-gray-900">{{ balance.left }}</span>
									<span class="text-gray-500"> {{ __("of {0} days", [balance.total]) }}</span>
								</span>
							</div>
						</div>

						<QuickLinks :items="visibleQuickLinks" :title="__('Quick Links')" />
					</aside>

					<main class="w-full flex-1 min-w-0 flex flex-col gap-4">
						<section v-if="isApprover" class="hidden lg:flex rounded-lg border bg-white p-4 flex-col gap-3">
							<div class="flex flex-row items-center gap-2">
								<h3 class="text-base font-semibold text-gray-900">{{ __("Waiting for your approval") }}</h3>
								<span
									v-if="waitingCount"
									class="rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white"
								>
									{{ waitingCount }}
								</span>
							</div>
							<LeaveApprovals layout="table" />
							<OtherApprovals />
						</section>

						<TeamToday />

						<div class="rounded-lg border bg-white p-4">
							<RequestPanel />
						</div>
					</main>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, markRaw } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"
import { FeatherIcon } from "frappe-ui"

import CheckInPanel from "@/components/CheckInPanel.vue"
import QuickLinks from "@/components/QuickLinks.vue"
import BaseLayout from "@/components/BaseLayout.vue"
import RequestPanel from "@/components/RequestPanel.vue"
import HomeNotices from "@/components/HomeNotices.vue"
import LeaveApprovals from "@/components/LeaveApprovals.vue"
import OtherApprovals from "@/components/OtherApprovals.vue"
import TeamToday from "@/components/TeamToday.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import ShiftIcon from "@/components/icons/ShiftIcon.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import EmployeeAdvanceIcon from "@/components/icons/EmployeeAdvanceIcon.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"

import { homeData } from "@/data/home"
import { leaveBalance } from "@/data/leaves"
import { showAttendanceRequests, showExpenses, showSalary } from "@/utils/navigation"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

homeData.reload()
leaveBalance.reload()
onIonViewWillEnter(() => homeData.reload())

const waitingCount = computed(() => homeData.data?.leave_approvals?.length || 0)
const isApprover = computed(
	() =>
		Boolean(homeData.data?.team) ||
		waitingCount.value > 0 ||
		(homeData.data?.other_approvals || []).some((row) => row.count)
)

const balances = computed(() =>
	Object.entries(leaveBalance.data || {}).map(([type, allocation]) => ({
		type,
		left: allocation.balance_leaves,
		total: allocation.allocated_leaves,
	}))
)

const quickLinks = [
	{
		icon: markRaw(AttendanceIcon),
		title: __("Request Attendance"),
		route: "AttendanceRequestFormView",
	},
	{
		icon: markRaw(ShiftIcon),
		title: __("Request a Shift"),
		route: "ShiftRequestFormView",
	},
	{
		icon: markRaw(LeaveIcon),
		title: __("Request Leave"),
		route: "LeaveApplicationFormView",
	},
	{
		icon: markRaw(ExpenseIcon),
		title: __("Claim an Expense"),
		route: "ExpenseClaimFormView",
	},
	{
		icon: markRaw(EmployeeAdvanceIcon),
		title: __("Request an Advance"),
		route: "EmployeeAdvanceFormView",
	},
	{
		icon: markRaw(SalaryIcon),
		title: __("View Salary Slips"),
		route: "SalarySlipsDashboard",
	},
]

// Expenses (claims, advances) and Salary Slips only when HR Settings show them in the app
// ... and Attendance / Shift requests
const EXPENSE_ROUTES = ["ExpenseClaimFormView", "EmployeeAdvanceFormView"]
const REQUEST_ROUTES = ["AttendanceRequestFormView", "ShiftRequestFormView"]
const visibleQuickLinks = computed(() =>
	quickLinks.filter(
		(link) =>
			(showExpenses.value || !EXPENSE_ROUTES.includes(link.route)) &&
			(showSalary.value || link.route !== "SalarySlipsDashboard") &&
			(showAttendanceRequests.value || !REQUEST_ROUTES.includes(link.route))
	)
)
</script>

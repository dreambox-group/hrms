<template>
	<BaseLayout>
		<template #body>
			<div class="flex w-full flex-col gap-5 px-4 pb-24 pt-5 lg:gap-6 lg:px-6 lg:pt-8">
				<div>
					<div class="text-sm font-medium text-gray-700">{{ dayjs().format("dddd, D MMMM YYYY") }}</div>
					<h1 class="mt-1 text-2xl font-bold tracking-tight text-ink lg:text-[30px]">
						{{ __("Hello, {0}", [employee?.data?.first_name]) }}
					</h1>
				</div>

				<div class="flex flex-col items-start gap-5 lg:flex-row lg:gap-6">
					<div class="flex w-full min-w-0 flex-1 flex-col gap-5 lg:gap-6">
						<CheckInPanel />
						<TodoList :limit="isDesktop ? 0 : 2" />
						<TeamToday />
					</div>
					<aside class="flex w-full flex-col gap-5 lg:w-[340px] lg:flex-none lg:gap-6">
						<HomeLeaveCard />
						<AroundOffice />
						<MyRequestsCard />
						<QuickLinks v-if="extraLinks.length" :items="extraLinks" :title="__('More')" />
					</aside>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, markRaw } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"

import BaseLayout from "@/components/BaseLayout.vue"
import CheckInPanel from "@/components/CheckInPanel.vue"
import TodoList from "@/components/TodoList.vue"
import TeamToday from "@/components/TeamToday.vue"
import HomeLeaveCard from "@/components/HomeLeaveCard.vue"
import AroundOffice from "@/components/AroundOffice.vue"
import MyRequestsCard from "@/components/MyRequestsCard.vue"
import QuickLinks from "@/components/QuickLinks.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import ShiftIcon from "@/components/icons/ShiftIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import EmployeeAdvanceIcon from "@/components/icons/EmployeeAdvanceIcon.vue"

import { useIsDesktop } from "@/composables/useIsDesktop"
import { homeData } from "@/data/home"
import { leaveBalance, myLeaves } from "@/data/leaves"
import { showAttendanceRequests, showExpenses } from "@/utils/navigation"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")
const isDesktop = useIsDesktop()

homeData.reload()
leaveBalance.reload()
onIonViewWillEnter(() => {
	homeData.reload()
	myLeaves.reload()
})

// requests that HR Settings can switch on for the app; leave has its own card
const extraLinks = computed(() =>
	[
		showAttendanceRequests.value && {
			icon: markRaw(AttendanceIcon),
			title: __("Request Attendance"),
			route: "AttendanceRequestFormView",
		},
		showAttendanceRequests.value && {
			icon: markRaw(ShiftIcon),
			title: __("Request a Shift"),
			route: "ShiftRequestFormView",
		},
		showExpenses.value && { icon: markRaw(ExpenseIcon), title: __("Claim an Expense"), route: "ExpenseClaimFormView" },
		showExpenses.value && {
			icon: markRaw(EmployeeAdvanceIcon),
			title: __("Request an Advance"),
			route: "EmployeeAdvanceFormView",
		},
	].filter(Boolean)
)
</script>

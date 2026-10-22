<template>
	<BaseLayout :pageTitle="__('Leaves')">
		<template #actions>
			<button
				type="button"
				class="flex min-h-[44px] items-center gap-2 rounded-xl bg-brand-600 px-5 text-[15px] font-semibold text-white hover:bg-brand-700"
				@click="openLeaveRequest(router, isDesktop)"
			>
				<FeatherIcon name="plus" class="h-4 w-4" />
				{{ __("Request leave") }}
			</button>
		</template>
		<template #body>
			<div class="flex w-full flex-col gap-5 px-4 pb-24 pt-5 lg:gap-6 lg:px-6">
				<!-- balances -->
				<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
					<section
						v-for="row in balances"
						:key="row.type"
						class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-5 lg:p-6"
					>
						<h2 class="text-base font-semibold text-ink">{{ row.type }}</h2>
						<div class="flex flex-row items-baseline gap-2">
							<span class="text-[44px] font-bold leading-none tracking-tight text-ink">{{ row.left }}</span>
							<span class="text-[15px] text-gray-700">{{ __("of {0} days left", [row.total]) }}</span>
						</div>
						<LeaveBar :row="row" />
					</section>
					<section
						v-for="type in unpaidTypes"
						:key="type"
						class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-5 lg:p-6"
					>
						<h2 class="text-base font-semibold text-ink">{{ type }}</h2>
						<p class="text-[15px] leading-relaxed text-gray-700">
							{{ __("No limit. Each day is deducted from your salary.") }}
						</p>
					</section>
				</div>

				<div class="flex flex-col items-start gap-5 lg:flex-row lg:gap-6">
					<!-- requests -->
					<section class="flex w-full min-w-0 flex-1 flex-col gap-3 rounded-2xl border border-line bg-white p-4 lg:p-6">
						<div class="flex flex-row flex-wrap items-center justify-between gap-3">
							<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("My requests") }}</h2>
							<div role="tablist" :aria-label="__('Filter')" class="flex flex-row gap-1 overflow-x-auto rounded-xl bg-[#F1F3F0] p-1">
								<button
									v-for="tab in TABS"
									:key="tab.value"
									type="button"
									role="tab"
									:aria-selected="activeTab === tab.value"
									:class="[
										'min-h-[36px] whitespace-nowrap rounded-lg px-3.5 text-sm',
										activeTab === tab.value ? 'bg-white font-semibold text-ink shadow-sm' : 'font-medium text-gray-700',
									]"
									@click="activeTab = tab.value"
								>
									{{ tab.label }}
								</button>
							</div>
						</div>

						<button
							v-for="row in rows"
							:key="row.name"
							type="button"
							:aria-pressed="selected === row.name"
							:class="[
								'flex flex-row items-center gap-4 rounded-xl border p-3.5 text-left lg:p-4',
								isDesktop && selected === row.name ? 'border-brand-600 bg-brand-50' : 'border-line bg-white hover:border-gray-400',
							]"
							@click="select(row.name)"
						>
							<span class="flex h-11 w-11 flex-none flex-col items-center justify-center rounded-xl bg-page">
								<span class="text-[11px] font-semibold uppercase text-gray-700">{{ dayjs(row.from_date).format("MMM") }}</span>
								<span class="text-base font-bold leading-none text-ink">{{ dayjs(row.from_date).format("D") }}</span>
							</span>
							<span class="flex min-w-0 flex-1 flex-col gap-0.5">
								<span class="text-[15px] font-semibold text-ink">{{ row.leave_type }}</span>
								<span class="text-[13px] text-gray-700">{{ row.dates }}</span>
							</span>
							<span :class="['whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[row.tone]]">
								{{ row.label }}
							</span>
						</button>
						<div
							v-if="allLeaves.fetched && !rows.length"
							class="rounded-xl border border-dashed border-[#D5DAD4] p-6 text-center text-sm text-gray-700"
						>
							{{ __("No requests here.") }}
						</div>
						<router-link
							v-if="homeData.data?.team"
							:to="{ name: 'LeaveApplicationListView' }"
							class="self-start pt-1 text-sm font-medium text-brand-600"
						>
							{{ __("Team leave history") }}
						</router-link>
					</section>

					<aside class="flex w-full flex-col gap-5 lg:w-[360px] lg:flex-none lg:gap-6">
						<section v-if="isDesktop && selected" class="rounded-2xl border border-line bg-white p-5 lg:p-6">
							<LeaveDetail :name="selected" @changed="reloadAll" />
						</section>

						<section class="flex flex-col rounded-2xl border border-line bg-white p-4 lg:p-6">
							<div class="flex flex-row items-baseline justify-between pb-2">
								<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("Upcoming holidays") }}</h2>
								<button
									v-if="upcomingHolidays.length > 5"
									type="button"
									class="text-sm font-semibold text-brand-600"
									@click="showAllHolidays = !showAllHolidays"
								>
									{{ showAllHolidays ? __("Show less") : __("View all") }}
								</button>
							</div>
							<div
								v-for="holiday in shownHolidays"
								:key="holiday.holiday_date"
								class="flex flex-row justify-between gap-3 border-t border-[#EEF0EE] py-2.5 text-sm"
							>
								<span class="text-ink">{{ holiday.description }}</span>
								<span class="whitespace-nowrap font-semibold text-ink">{{ holidayDate(holiday.holiday_date) }}</span>
							</div>
							<div v-if="holidays.fetched && !upcomingHolidays.length" class="border-t border-[#EEF0EE] pt-3 text-sm text-gray-700">
								{{ __("No upcoming holidays.") }}
							</div>
						</section>
					</aside>
				</div>
			</div>

			<!-- phones: the request opens as a sheet -->
			<ion-modal
				v-if="!isDesktop"
				:is-open="Boolean(sheetFor)"
				:initial-breakpoint="1"
				:breakpoints="[0, 1]"
				@didDismiss="sheetFor = null"
			>
				<div class="max-h-[85vh] overflow-y-auto p-5">
					<LeaveDetail v-if="sheetFor" :name="sheetFor" @changed="reloadAll" />
				</div>
			</ion-modal>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { IonModal, onIonViewWillEnter } from "@ionic/vue"
import { createResource, FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import LeaveBar from "@/components/LeaveBar.vue"
import LeaveDetail from "@/components/LeaveDetail.vue"
import { useIsDesktop } from "@/composables/useIsDesktop"
import { leaveRequestOpen, openLeaveRequest } from "@/composables/leaveRequest"
import { homeData } from "@/data/home"
import { balanceRows, leaveBalance, myLeaves } from "@/data/leaves"
import { LEAVE_STATUS_LABEL, LEAVE_STATUS_TONE, TONE_CLASSES } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")
const router = useRouter()
const isDesktop = useIsDesktop()

const TABS = [
	{ value: "All", label: __("All") },
	{ value: "Open", label: __("Waiting") },
	{ value: "Approved", label: __("Approved") },
	{ value: "Rejected", label: __("Rejected") },
]
const activeTab = ref("All")
const selected = ref(null)
const sheetFor = ref(null)
const showAllHolidays = ref(false)

const allLeaves = createResource({
	url: "hrms.api.get_leave_applications",
	params: { employee: employee.data.name, limit: 100 },
	auto: true,
})
const leaveTypes = createResource({
	url: "hrms.api.get_leave_types",
	params: { employee: employee.data.name, date: dayjs().format("YYYY-MM-DD") },
	auto: true,
})
const holidays = createResource({
	url: "hrms.api.get_holidays_for_employee",
	params: { employee: employee.data.name },
	auto: true,
})
leaveBalance.reload()

const balances = computed(() => balanceRows(leaveBalance.data))
const unpaidTypes = computed(() => (leaveTypes.data || []).filter((type) => !leaveBalance.data?.[type]))

const rows = computed(() =>
	(allLeaves.data || [])
		.filter((row) => activeTab.value === "All" || row.status === activeTab.value)
		.map((row) => {
			const from = dayjs(row.from_date).format("ddd D MMM")
			const range = row.from_date === row.to_date ? from : `${from} – ${dayjs(row.to_date).format("ddd D MMM")}`
			return {
				...row,
				dates: `${range} · ${row.total_leave_days == 1 ? __("1 day") : __("{0} days", [row.total_leave_days])}`,
				tone: LEAVE_STATUS_TONE[row.status] || "neutral",
				label: __(LEAVE_STATUS_LABEL[row.status] || row.status),
			}
		})
)

// wide screens show the first request's details straight away
watch(
	() => allLeaves.data,
	(data) => {
		if (!selected.value && data?.length) selected.value = data[0].name
	}
)

function select(name) {
	selected.value = name
	if (!isDesktop.value) sheetFor.value = name
}

function reloadAll() {
	allLeaves.reload()
	leaveBalance.reload()
	myLeaves.reload()
	homeData.reload()
}
onIonViewWillEnter(() => {
	allLeaves.reload()
	leaveBalance.reload()
})
// a request sent from the side panel shows up here straight away
watch(leaveRequestOpen, (open) => !open && reloadAll())

const upcomingHolidays = computed(() =>
	(holidays.data || []).filter((row) => !dayjs(row.holiday_date).isBefore(dayjs(), "day"))
)
const shownHolidays = computed(() => (showAllHolidays.value ? upcomingHolidays.value : upcomingHolidays.value.slice(0, 5)))
function holidayDate(date) {
	const value = dayjs(date)
	return value.isSame(dayjs(), "year") ? value.format("ddd D MMM") : value.format("ddd D MMM YYYY")
}
</script>

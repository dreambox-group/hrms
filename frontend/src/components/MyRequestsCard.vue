<template>
	<section :aria-label="__('My requests')" class="flex flex-col rounded-2xl border border-line bg-white p-4 lg:p-6">
		<div class="flex flex-row items-baseline justify-between pb-2">
			<h3 class="text-base font-bold text-ink lg:text-lg">{{ __("My requests") }}</h3>
			<router-link :to="{ name: 'LeavesDashboard' }" class="text-sm font-semibold text-brand-600">
				{{ __("All requests") }}
			</router-link>
		</div>
		<router-link
			v-for="row in rows"
			:key="row.name"
			:to="{ name: 'LeaveApplicationDetailView', params: { id: row.name } }"
			class="flex flex-row items-center justify-between gap-3 border-t border-[#EEF0EE] py-3 hover:bg-gray-50"
		>
			<div>
				<div class="text-[15px] font-medium text-ink">{{ row.leave_type }}</div>
				<div class="mt-0.5 text-[13px] text-gray-700">{{ row.dates }}</div>
			</div>
			<span :class="['whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[row.tone]]">
				{{ row.label }}
			</span>
		</router-link>
		<div v-if="myLeaves.fetched && !rows.length" class="border-t border-[#EEF0EE] pt-3 text-sm text-gray-700">
			{{ __("No leave requests yet.") }}
		</div>
	</section>
</template>

<script setup>
import { computed, inject } from "vue"

import { myLeaves } from "@/data/leaves"
import { LEAVE_STATUS_LABEL, LEAVE_STATUS_TONE, TONE_CLASSES } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const rows = computed(() =>
	(myLeaves.data || []).slice(0, 3).map((row) => {
		const from = dayjs(row.from_date).format("ddd D MMM")
		const range = row.from_date === row.to_date ? from : `${from} – ${dayjs(row.to_date).format("D MMM")}`
		const days = row.total_leave_days == 1 ? __("1 day") : __("{0} days", [row.total_leave_days])
		return {
			...row,
			dates: `${range} · ${days}`,
			tone: LEAVE_STATUS_TONE[row.status] || "neutral",
			label: __(LEAVE_STATUS_LABEL[row.status] || row.status),
		}
	})
)
</script>

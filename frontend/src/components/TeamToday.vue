<template>
	<div v-if="team" class="rounded-lg border bg-white p-4 flex flex-col gap-3">
		<div class="flex flex-row justify-between items-baseline gap-3">
			<h3 class="text-base font-semibold text-gray-900">{{ __("Your team today") }}</h3>
			<span class="text-sm text-gray-500">
				{{ __("{0} of {1} checked in", [team.checked_in, team.total]) }}
			</span>
		</div>
		<div class="text-xs text-gray-500">{{ team.departments.join(", ") }}</div>
		<div v-if="!team.rows.length" class="text-sm text-gray-500">{{ __("Nobody else is in your departments.") }}</div>
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
			<div
				v-for="row in team.rows"
				:key="row.employee"
				class="flex flex-row justify-between items-center gap-2 rounded border px-3 py-2 text-sm"
			>
				<span class="font-medium text-gray-900 truncate">{{ row.employee_name }}</span>
				<span :class="['rounded-full px-2 py-0.5 text-xs font-semibold whitespace-nowrap', STATUS_CLASSES[row.status]]">
					{{ statusText(row) }}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"

import { homeData } from "@/data/home"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const team = computed(() => homeData.data?.team)

const STATUS_CLASSES = {
	"Checked in": "bg-green-100 text-green-800",
	Late: "bg-orange-100 text-orange-800",
	"Not yet in": "bg-gray-100 text-gray-700",
	"On leave": "bg-blue-100 text-blue-800",
	Holiday: "bg-gray-100 text-gray-700",
	"No shift": "bg-gray-100 text-gray-700",
}

function statusText(row) {
	if (row.checked_in_at) return `${__(row.status)} ${dayjs(row.checked_in_at).format("HH:mm")}`
	if (row.status === "On leave" && row.leave_label) return row.leave_label
	return __(row.status)
}
</script>

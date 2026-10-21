<template>
	<div v-if="notices.length" class="grid grid-cols-1 lg:grid-cols-4 gap-2 lg:gap-3">
		<component
			:is="notice.to ? 'router-link' : 'div'"
			v-for="notice in notices"
			:key="notice.title"
			:to="notice.to"
			class="flex flex-row gap-3 items-start rounded-lg border bg-white px-4 py-3 text-sm"
		>
			<span :class="['mt-1.5 h-2 w-2 flex-none rounded-full', notice.dot]"></span>
			<span>
				<span class="font-semibold text-gray-900">{{ notice.title }}</span>
				<span class="block text-gray-600">{{ notice.text }}</span>
			</span>
		</component>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"

import { homeData } from "@/data/home"

const __ = inject("$translate")

const notices = computed(() => {
	const data = homeData.data
	if (!data) return []
	const list = []

	if (data.on_leave_today.length) {
		list.push({
			title: __("On leave today"),
			text: data.on_leave_today.map((row) => `${row.employee_name} (${row.label})`).join(", "),
			dot: "bg-blue-500",
		})
	}
	if (data.birthdays_today.length) {
		list.push({
			title: __("Birthday today"),
			text: data.birthdays_today.join(", "),
			dot: "bg-pink-500",
		})
	}
	const waiting = data.leave_approvals.length
	if (waiting) {
		list.push({
			title: __("Leave waiting for you"),
			text: waiting === 1 ? __("1 request") : __("{0} requests", [waiting]),
			dot: "bg-red-500",
			to: { name: "Approvals" },
		})
	}
	if (data.team) {
		list.push({
			title: __("Your team's check-ins"),
			text: data.team.late
				? __("{0} of {1} in · {2} late", [data.team.checked_in, data.team.total, data.team.late])
				: __("{0} of {1} in", [data.team.checked_in, data.team.total]),
			dot: "bg-green-500",
		})
	}
	return list
})
</script>

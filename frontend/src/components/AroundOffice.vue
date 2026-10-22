<template>
	<section
		:aria-label="__('Around the office')"
		class="flex flex-col gap-3.5 rounded-2xl border border-line bg-white p-4 lg:p-6"
	>
		<h3 class="text-base font-bold text-ink lg:text-lg">{{ __("Around the office") }}</h3>
		<div v-for="row in rows" :key="row.title" class="flex flex-row items-start gap-3">
			<span :class="['flex h-8 w-8 flex-none items-center justify-center rounded-lg', row.chip]">
				<FeatherIcon :name="row.icon" class="h-[18px] w-[18px]" />
			</span>
			<div class="text-sm leading-snug text-ink">
				<div class="font-semibold">{{ row.title }}</div>
				<div class="text-gray-700">{{ row.text }}</div>
			</div>
		</div>
		<div v-if="!rows.length" class="text-sm text-gray-700">{{ __("Nothing special today.") }}</div>
	</section>
</template>

<script setup>
import { computed, inject } from "vue"
import { FeatherIcon } from "frappe-ui"

import { homeData } from "@/data/home"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

// everyone sees this: who is away, birthdays and the next holiday
const rows = computed(() => {
	const data = homeData.data
	if (!data) return []
	const list = []
	if (data.on_leave_today?.length) {
		list.push({
			title: __("Out today"),
			text: data.on_leave_today
				.map((row) =>
					row.to_date && row.to_date !== data.date
						? __("{0} · {1}, until {2}", [row.employee_name, row.label, dayjs(row.to_date).format("ddd D MMM")])
						: `${row.employee_name} · ${row.label}`
				)
				.join("; "),
			icon: "sun",
			chip: "bg-[#E4ECFB] text-[#1E55B8]",
		})
	}
	if (data.birthdays_today?.length) {
		list.push({
			title: __("Birthday today"),
			text: data.birthdays_today.join(", "),
			icon: "gift",
			chip: "bg-[#FCE8F1] text-[#A3215F]",
		})
	}
	if (data.next_holiday) {
		list.push({
			title: __("Next holiday"),
			text: `${data.next_holiday.description} · ${dayjs(data.next_holiday.holiday_date).format("ddd D MMM")}`,
			icon: "calendar",
			chip: "bg-[#EEF0EE] text-gray-700",
		})
	}
	return list
})
</script>

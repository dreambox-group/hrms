<template>
	<section v-if="penalties" :aria-label="__('This pay period')" class="flex flex-col gap-1 rounded-2xl border border-line bg-white p-4 lg:p-6">
		<div class="pb-2">
			<h3 class="text-base font-bold text-ink lg:text-lg">{{ __("This pay period") }}</h3>
			<p class="text-[13px] text-gray-700">{{ period }}</p>
		</div>

		<div v-for="row in rows" :key="row.key" class="border-t border-[#EEF0EE] py-2.5">
			<button
				type="button"
				class="flex w-full flex-row items-center justify-between gap-3 text-left disabled:cursor-default"
				:disabled="!row.dates.length"
				:aria-expanded="open === row.key"
				@click="open = open === row.key ? null : row.key"
			>
				<span class="flex flex-row items-center gap-2 text-sm text-ink">
					<span :class="['h-2.5 w-2.5 rounded-full', row.count ? TONE_DOTS[row.tone] : 'bg-[#C9CEC8]']"></span>
					{{ row.label }}
				</span>
				<span class="flex flex-row items-center gap-1.5">
					<span :class="['text-xl font-bold leading-none', row.count ? TONE_TEXT[row.tone] : 'text-gray-500']">{{ row.count }}</span>
					<FeatherIcon v-if="row.dates.length" :name="open === row.key ? 'chevron-up' : 'chevron-down'" class="h-4 w-4 text-gray-600" />
				</span>
			</button>
			<div v-if="open === row.key" class="flex flex-row flex-wrap gap-1.5 pl-[18px] pt-2">
				<span v-for="date in row.dates" :key="date" class="rounded-full bg-page px-2.5 py-1 text-xs font-medium text-ink">{{ date }}</span>
			</div>
		</div>

		<p class="pt-1 text-[13px] leading-snug text-gray-700">
			{{
				total
					? __("Each of these is deducted from your pay for this period. Something wrong? Talk to HR.")
					: __("Nothing to deduct so far. Keep it up!")
			}}
		</p>
	</section>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { FeatherIcon } from "frappe-ui"

import { homeData } from "@/data/home"
import { TONE_DOTS } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const TONE_TEXT = { warn: "text-[#8A4B00]", bad: "text-[#A8231A]" }
const open = ref(null)

const penalties = computed(() => homeData.data?.penalties || null)
const period = computed(() => {
	const p = penalties.value
	return p ? `${dayjs(p.period_start).format("D MMM")} – ${dayjs(p.period_end).format("D MMM YYYY")}` : ""
})

const day = (date) => dayjs(date).format("ddd D MMM")
const rows = computed(() => {
	const p = penalties.value
	if (!p) return []
	const unpaidDays = p.unpaid_leave.reduce((sum, row) => sum + row.days, 0)
	return [
		{ key: "late", label: __("Late days"), tone: "warn", count: p.late.length, dates: p.late.map(day) },
		{
			key: "unpaid",
			label: __("Unpaid leave days"),
			tone: "bad",
			count: unpaidDays,
			dates: p.unpaid_leave.map((row) =>
				row.from_date === row.to_date ? `${day(row.from_date)} · ${row.leave_type}` : `${day(row.from_date)} – ${day(row.to_date)} · ${row.leave_type}`
			),
		},
		{ key: "no_checkin", label: __("Days without check-in"), tone: "bad", count: p.no_checkin.length, dates: p.no_checkin.map(day) },
	]
})
const total = computed(() => rows.value.reduce((sum, row) => sum + row.count, 0))
</script>

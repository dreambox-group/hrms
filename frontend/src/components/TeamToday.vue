<template>
	<section
		v-if="team"
		:aria-label="__('Team today')"
		class="flex flex-col gap-1 rounded-2xl border border-line bg-white p-4 lg:p-6"
	>
		<div class="flex flex-row flex-wrap items-baseline justify-between gap-2 pb-2">
			<div>
				<h3 class="text-base font-bold text-ink lg:text-lg">{{ __("Team today") }}</h3>
				<div class="mt-0.5 text-[13px] text-gray-700">
					{{ team.departments.join(", ") }} ·
					{{ team.rows.length == 1 ? __("1 person") : __("{0} people", [team.rows.length]) }}
				</div>
			</div>
			<span class="text-sm text-gray-700">{{ summary }}</span>
		</div>

		<div v-if="!team.rows.length" class="py-2 text-sm text-gray-700">
			{{ __("Nobody else is in your departments.") }}
		</div>

		<div
			v-for="group in groups"
			:key="group.status"
			class="flex flex-col gap-2 border-t border-[#EEF0EE] py-3 lg:flex-row lg:items-start lg:gap-3"
		>
			<div class="flex flex-row items-center gap-2 lg:w-[180px] lg:flex-none lg:pt-2">
				<span :class="['h-2 w-2 rounded-full', TONE_DOTS[group.tone]]"></span>
				<span class="text-sm font-semibold text-ink">{{ group.label }}</span>
				<span class="text-[13px] text-gray-700">{{ group.rows.length }}</span>
			</div>
			<div class="flex flex-1 flex-row flex-wrap gap-2">
				<div
					v-for="row in group.rows"
					:key="row.employee"
					class="flex flex-row items-center gap-2 rounded-full border border-line py-1 pl-1 pr-3.5"
				>
					<span
						class="flex h-[30px] w-[30px] items-center justify-center rounded-full text-[11px] font-semibold text-ink"
						:style="{ background: avatarColour(row.employee_name) }"
					>
						{{ initials(row.employee_name) }}
					</span>
					<span class="text-sm text-ink">{{ row.employee_name }}</span>
					<span v-if="detail(row)" :class="['text-[13px] font-medium', TONE_TEXT[group.tone]]">
						{{ detail(row) }}
					</span>
				</div>
			</div>
		</div>

		<div v-if="quiet.length" class="border-t border-[#EEF0EE] pt-3">
			<button
				type="button"
				class="flex flex-row items-center gap-2 py-1.5 text-sm font-medium text-gray-700"
				:aria-expanded="showQuiet"
				@click="showQuiet = !showQuiet"
			>
				<FeatherIcon :name="showQuiet ? 'chevron-down' : 'chevron-right'" class="h-4 w-4" />
				{{ __("No schedule today · {0}", [quiet.length]) }}
			</button>
			<div v-if="showQuiet" class="flex flex-row flex-wrap gap-2 pl-6 pt-2">
				<span
					v-for="row in quiet"
					:key="row.employee"
					class="rounded-full bg-[#EEF0EE] px-3 py-1.5 text-sm text-gray-700"
				>
					{{ row.employee_name }}<template v-if="row.status === 'Holiday'"> · {{ __("holiday") }}</template>
				</span>
			</div>
		</div>
	</section>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { FeatherIcon } from "frappe-ui"

import { homeData } from "@/data/home"
import { TONE_DOTS, avatarColour, initials } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const team = computed(() => homeData.data?.team)
const showQuiet = ref(false)

const TONE_TEXT = {
	ok: "text-[#0F6B4C]",
	warn: "text-[#8A4B00]",
	info: "text-[#1E55B8]",
	neutral: "text-gray-700",
}

// who still needs attention first, then who is away, then who is in
const GROUPS = [
	{ status: "Not checked in", label: __("Not checked in"), tone: "neutral" },
	{ status: "Late", label: __("Late"), tone: "warn" },
	{ status: "On leave", label: __("On leave"), tone: "info" },
	{ status: "Checked in", label: __("Checked in"), tone: "ok" },
]

const groups = computed(() =>
	GROUPS.map((group) => ({
		...group,
		rows: (team.value?.rows || []).filter((row) => row.status === group.status),
	})).filter((group) => group.rows.length)
)
const quiet = computed(() =>
	(team.value?.rows || []).filter((row) => ["No shift", "Holiday"].includes(row.status))
)

const summary = computed(() => {
	const count = (status) => (team.value?.rows || []).filter((row) => row.status === status).length
	return [
		__("{0} in", [count("Checked in") + count("Late")]),
		count("Late") && __("{0} late", [count("Late")]),
		count("On leave") && __("{0} on leave", [count("On leave")]),
		__("{0} not checked in", [count("Not checked in")]),
	]
		.filter(Boolean)
		.join(" · ")
})

function detail(row) {
	if (row.checked_in_at) return dayjs(row.checked_in_at).format("HH:mm")
	if (row.status === "On leave") return row.leave_label
	return ""
}
</script>

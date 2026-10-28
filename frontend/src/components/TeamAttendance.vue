<template>
	<section :aria-label="__('Team attendance')" class="flex flex-col gap-1 rounded-2xl border border-line bg-white p-4 lg:p-6">
		<div class="flex flex-row flex-wrap items-baseline justify-between gap-2 pb-2">
			<div>
				<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("Team attendance · {0}", [month.format("MMMM YYYY")]) }}</h2>
				<p class="text-[13px] text-gray-700">{{ __("Tap someone to see their days on the calendar.") }}</p>
			</div>
		</div>

		<!-- wide screens: a table of days by kind -->
		<table v-if="isDesktop" class="w-full table-fixed border-collapse text-sm">
			<thead>
				<tr class="border-b border-line text-left text-xs font-semibold uppercase tracking-[0.06em] text-gray-700">
					<th scope="col" class="w-[34%] py-2">{{ __("Employee") }}</th>
					<th v-for="kind in KINDS" :key="kind.key" scope="col" class="py-2 text-center">
						<span class="inline-flex flex-row items-center gap-1.5">
							<span :class="['h-2 w-2 rounded-full', TONE_DOTS[kind.tone]]"></span>{{ kind.label }}
						</span>
					</th>
				</tr>
			</thead>
			<tbody>
				<tr
					v-for="row in team.data || []"
					:key="row.employee"
					:class="['cursor-pointer border-b border-[#EEF0EE] last:border-0 hover:bg-page', viewing === row.employee ? 'bg-brand-50' : '']"
					@click="emit('select', row)"
				>
					<th scope="row" class="py-2.5 text-left font-normal">
						<button type="button" class="flex w-full flex-row items-center gap-2.5 text-left" :aria-pressed="viewing === row.employee">
							<span
								class="flex h-8 w-8 flex-none items-center justify-center rounded-full text-xs font-semibold text-ink"
								:style="{ background: avatarColour(row.employee_name) }"
							>
								{{ initials(row.employee_name) }}
							</span>
							<span class="flex min-w-0 flex-col">
								<span class="truncate font-semibold text-ink">{{ row.employee_name }}</span>
								<span class="truncate text-xs text-gray-700">{{ row.department || "" }}</span>
							</span>
						</button>
					</th>
					<td
						v-for="kind in KINDS"
						:key="kind.key"
						:class="['py-2.5 text-center text-[15px]', row.counts[kind.key] && kind.alert ? 'font-bold text-[#A8231A]' : 'font-semibold text-ink']"
					>
						{{ row.counts[kind.key] }}
					</td>
				</tr>
			</tbody>
		</table>

		<!-- phones: one row per person with small counts -->
		<template v-else>
			<button
				v-for="row in team.data || []"
				:key="row.employee"
				type="button"
				:aria-pressed="viewing === row.employee"
				:class="['flex flex-col gap-2 border-t border-[#EEF0EE] py-3 text-left', viewing === row.employee ? 'bg-brand-50' : '']"
				@click="emit('select', row)"
			>
				<span class="flex flex-row items-center gap-2.5">
					<span
						class="flex h-8 w-8 flex-none items-center justify-center rounded-full text-xs font-semibold text-ink"
						:style="{ background: avatarColour(row.employee_name) }"
					>
						{{ initials(row.employee_name) }}
					</span>
					<span class="truncate text-[15px] font-semibold text-ink">{{ row.employee_name }}</span>
				</span>
				<span class="flex flex-row flex-wrap gap-1.5 pl-[42px]">
					<span
						v-for="kind in KINDS"
						:key="kind.key"
						:class="['rounded-full px-2 py-0.5 text-xs font-semibold', row.counts[kind.key] ? TONE_CLASSES[kind.tone] : 'bg-[#F6F7F5] text-gray-500']"
					>
						{{ kind.label }} {{ row.counts[kind.key] }}
					</span>
				</span>
			</button>
		</template>

		<div v-if="team.fetched && !team.data?.length" class="py-2 text-sm text-gray-700">{{ __("Nobody else is in your departments.") }}</div>
		<div v-if="team.loading && !team.data" class="py-2 text-sm text-gray-700">{{ __("Loading…") }}</div>
	</section>
</template>

<script setup>
import { inject, watch } from "vue"
import { latestResource } from "@/composables/latestResource"

import { useIsDesktop } from "@/composables/useIsDesktop"
import { avatarColour, initials, TONE_CLASSES, TONE_DOTS } from "@/utils/status"

const __ = inject("$translate")
const isDesktop = useIsDesktop()

const props = defineProps({
	month: { type: Object, required: true },
	viewing: { type: String, default: "" },
})
const emit = defineEmits(["select"])

// as the calendar colours them
const KINDS = [
	{ key: "on_time", label: __("On time"), tone: "ok" },
	{ key: "late", label: __("Late"), tone: "warn" },
	{ key: "on_leave", label: __("Leave"), tone: "info" },
	{ key: "absent", label: __("Absent"), tone: "bad", alert: true },
	{ key: "no_checkin", label: __("No check-in"), tone: "neutral" },
]

const team = latestResource({ url: "hrms.api.employee_app.get_team_attendance" })
watch(
	() => props.month,
	(month) =>
		team.submit({ from_date: month.format("YYYY-MM-DD"), to_date: month.endOf("month").format("YYYY-MM-DD") }),
	{ immediate: true }
)
</script>

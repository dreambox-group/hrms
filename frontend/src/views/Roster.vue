<template>
	<BaseLayout :pageTitle="__('Roster')">
		<template #actions>
			<div class="flex flex-row items-center gap-2">
				<button
					type="button"
					class="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-white text-ink hover:bg-gray-50"
					:aria-label="__('Previous week')"
					@click="moveWeek(-1)"
				>
					<FeatherIcon name="chevron-left" class="h-4 w-4" />
				</button>
				<span class="min-w-[150px] text-center text-sm font-semibold text-ink">{{ weekLabel }}</span>
				<button
					type="button"
					class="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-white text-ink hover:bg-gray-50"
					:aria-label="__('Next week')"
					@click="moveWeek(1)"
				>
					<FeatherIcon name="chevron-right" class="h-4 w-4" />
				</button>
				<button
					v-if="!isThisWeek"
					type="button"
					class="min-h-[40px] rounded-xl px-3 text-sm font-semibold text-brand-600 hover:text-brand-700"
					@click="goToThisWeek"
				>
					{{ __("This week") }}
				</button>
			</div>
		</template>
		<template #body>
			<div class="flex w-full flex-col gap-4 px-4 pb-24 pt-5 lg:gap-5 lg:px-6">
				<!-- find someone -->
				<div class="flex flex-col gap-2.5 sm:flex-row">
					<input
						v-model="search"
						type="search"
						:placeholder="__('Search by name')"
						:aria-label="__('Search by name')"
						class="min-h-[44px] flex-1 rounded-xl border border-[#D5DAD4] bg-white px-3.5 text-[15px] text-ink focus:border-brand-600 focus:ring-brand-600"
					/>
					<select
						v-model="department"
						:aria-label="__('Department')"
						class="min-h-[44px] rounded-xl border border-[#D5DAD4] bg-white px-3.5 text-[15px] text-ink focus:border-brand-600 focus:ring-brand-600 sm:w-[260px]"
					>
						<option value="">{{ __("All departments") }}</option>
						<option v-for="name in departments" :key="name" :value="name">{{ name }}</option>
					</select>
				</div>

				<div v-if="roster.error" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
					{{ __("The roster could not be loaded.") }}
				</div>

				<!-- wide screens: everyone × the week -->
				<section v-if="isDesktop" class="overflow-x-auto rounded-2xl border border-line bg-white">
					<table class="w-full min-w-[900px] table-fixed border-collapse text-sm">
						<thead>
							<tr class="border-b border-line">
								<th scope="col" class="sticky left-0 w-[220px] bg-white px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.06em] text-gray-700">
									{{ __("Employee") }}
								</th>
								<th
									v-for="date in dates"
									:key="date"
									scope="col"
									:class="['px-2 py-3 text-center text-xs font-semibold', isToday(date) ? 'text-brand-700' : 'text-gray-700']"
								>
									<div class="uppercase tracking-[0.06em]">{{ dayjs(date).format("ddd") }}</div>
									<div :class="['mt-0.5 text-[15px]', isToday(date) ? 'font-bold' : 'font-semibold text-ink']">
										{{ dayjs(date).format("D MMM") }}
									</div>
								</th>
							</tr>
						</thead>
						<tbody v-for="group in departmentGroups" :key="group.department">
							<tr class="border-b border-line bg-page">
								<th scope="colgroup" colspan="8" class="sticky left-0 px-4 py-2 text-left">
									<span class="text-sm font-bold text-ink">{{ group.label }}</span>
									<span class="ml-2 text-[13px] font-medium text-gray-700">{{ peopleLabel(group.rows.length) }}</span>
								</th>
							</tr>
							<tr v-for="row in group.rows" :key="row.employee" class="border-b border-[#EEF0EE] last:border-0">
								<th scope="row" class="sticky left-0 bg-white px-4 py-2.5 text-left font-normal">
									<div class="flex flex-row items-center gap-2.5">
										<span
											class="flex h-8 w-8 flex-none items-center justify-center rounded-full text-xs font-semibold text-ink"
											:style="{ background: avatarColour(row.employee_name) }"
										>
											{{ initials(row.employee_name) }}
										</span>
										<span class="truncate font-semibold text-ink">{{ row.employee_name }}</span>
									</div>
								</th>
								<td
									v-for="day in row.days"
									:key="day.date"
									:class="['px-1.5 py-2 text-center', isToday(day.date) ? 'bg-brand-50/60' : '']"
								>
									<span
										:class="['flex w-full min-w-0 flex-col rounded-lg px-1.5 py-1 text-xs font-semibold', cell(day).classes]"
										:title="cell(day).title"
									>
										<span class="truncate">{{ cell(day).label }}</span>
										<span v-if="cell(day).sub" class="truncate text-[11px] font-medium opacity-80">{{ cell(day).sub }}</span>
									</span>
								</td>
							</tr>
						</tbody>
					</table>
				</section>

				<!-- phones: one day at a time, grouped by where people are -->
				<template v-else>
					<div role="tablist" :aria-label="__('Day')" class="grid grid-cols-7 gap-1">
						<button
							v-for="date in dates"
							:key="date"
							type="button"
							role="tab"
							:aria-selected="selectedDate === date"
							:class="[
								'flex min-h-[56px] flex-col items-center justify-center rounded-xl border text-xs',
								selectedDate === date ? 'border-brand-600 bg-brand-50 text-brand-800' : 'border-line bg-white text-gray-700',
							]"
							@click="selectedDate = date"
						>
							<span class="font-semibold uppercase">{{ dayjs(date).format("dd") }}</span>
							<span :class="['text-base', isToday(date) ? 'font-bold' : 'font-semibold', selectedDate === date ? '' : 'text-ink']">
								{{ dayjs(date).format("D") }}
							</span>
						</button>
					</div>

					<section
						v-for="group in departmentGroups"
						:key="group.department"
						class="flex flex-col gap-1 rounded-2xl border border-line bg-white p-4"
					>
						<div class="flex flex-row items-center justify-between pb-1.5">
							<h2 class="text-[15px] font-bold text-ink">{{ group.label }}</h2>
							<span class="text-sm font-semibold text-gray-700">{{ group.rows.length }}</span>
						</div>
						<div
							v-for="row in group.rows"
							:key="row.employee"
							class="flex flex-row items-center gap-3 border-t border-[#EEF0EE] py-2.5"
						>
							<span
								class="flex h-9 w-9 flex-none items-center justify-center rounded-full text-xs font-semibold text-ink"
								:style="{ background: avatarColour(row.employee_name) }"
							>
								{{ initials(row.employee_name) }}
							</span>
							<span class="min-w-0 flex-1 truncate text-[15px] font-semibold text-ink">{{ row.employee_name }}</span>
							<span
								v-if="dayOf(row)"
								:class="['flex max-w-[55%] flex-col rounded-lg px-2.5 py-1 text-right text-xs font-semibold', cell(dayOf(row)).classes]"
							>
								<span class="truncate">{{ cell(dayOf(row)).label }}</span>
								<span v-if="cell(dayOf(row)).sub" class="truncate text-[11px] font-medium opacity-80">{{ cell(dayOf(row)).sub }}</span>
							</span>
						</div>
					</section>
				</template>

				<div
					v-if="roster.fetched && !shownRows.length"
					class="rounded-xl border border-dashed border-[#D5DAD4] p-6 text-center text-sm text-gray-700"
				>
					{{ __("Nobody matches.") }}
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"
import { createResource, FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { useIsDesktop } from "@/composables/useIsDesktop"
import { avatarColour, initials } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const isDesktop = useIsDesktop()

// weeks start on Monday
const thisMonday = () => {
	const today = dayjs()
	return today.subtract((today.day() + 6) % 7, "day").format("YYYY-MM-DD")
}
const weekStart = ref(thisMonday())
const selectedDate = ref(dayjs().format("YYYY-MM-DD"))
const search = ref("")
const department = ref("")

const roster = createResource({
	url: "hrms.api.employee_app.get_roster",
	makeParams: () => ({ start_date: weekStart.value, days: 7 }),
	auto: true,
})
onIonViewWillEnter(() => roster.reload())
watch(weekStart, () => roster.reload())

const dates = computed(() => roster.data?.dates || [])
const isToday = (date) => dayjs(date).isSame(dayjs(), "day")
const isThisWeek = computed(() => weekStart.value === thisMonday())
const weekLabel = computed(() => {
	const start = dayjs(weekStart.value)
	const end = start.add(6, "day")
	return start.month() === end.month()
		? `${start.format("D")} – ${end.format("D MMM YYYY")}`
		: `${start.format("D MMM")} – ${end.format("D MMM YYYY")}`
})

function moveWeek(step) {
	weekStart.value = dayjs(weekStart.value).add(step * 7, "day").format("YYYY-MM-DD")
	selectedDate.value = weekStart.value
}
function goToThisWeek() {
	weekStart.value = thisMonday()
	selectedDate.value = dayjs().format("YYYY-MM-DD")
}

const departments = computed(() =>
	[...new Set((roster.data?.employees || []).map((row) => row.department).filter(Boolean))].sort()
)
const shownRows = computed(() => {
	const query = search.value.trim().toLowerCase()
	return (roster.data?.employees || []).filter(
		(row) =>
			(!department.value || row.department === department.value) &&
			(!query || row.employee_name.toLowerCase().includes(query))
	)
})

// Shift Type colours (as in the desk Roster), with a fallback for shifts without one
const SHIFT_COLOURS = {
	Blue: "bg-[#E4ECFB] text-[#1E55B8]",
	Cyan: "bg-[#E0F4F7] text-[#0B6A78]",
	Fuchsia: "bg-[#FBE7F7] text-[#8E1F7C]",
	Green: "bg-[#E2F4EA] text-[#0F6B4C]",
	Lime: "bg-[#EEF6DA] text-[#4D6B0F]",
	Orange: "bg-[#FDEFD6] text-[#8A4B00]",
	Pink: "bg-[#FCE8F1] text-[#A3245E]",
	Red: "bg-[#FCE6E4] text-[#A8231A]",
	Violet: "bg-[#EDE7FB] text-[#5B33B0]",
	Yellow: "bg-[#FBF3D0] text-[#7A5C00]",
}
const FALLBACK = ["Green", "Blue", "Violet", "Cyan", "Orange", "Pink"]
function shiftColour(shift) {
	const colour = roster.data?.shift_types?.[shift]?.color
	if (SHIFT_COLOURS[colour]) return colour
	const sum = [...(shift || "")].reduce((total, char) => total + char.charCodeAt(0), 0)
	return FALLBACK[sum % FALLBACK.length]
}
const shiftClasses = (shift) => SHIFT_COLOURS[shiftColour(shift)]
const hours = (shift) => {
	const type = roster.data?.shift_types?.[shift]
	if (!type?.start_time) return ""
	const time = (value) => String(value).split(":").slice(0, 2).join(":").padStart(5, "0")
	return `${time(type.start_time)}–${time(type.end_time)}`
}

function cell(day) {
	if (day.on_leave) return { label: __("Leave"), classes: "bg-[#E4ECFB] text-[#1E55B8]", title: __("On leave") }
	if (day.holiday) return { label: __("Holiday"), sub: day.holiday, classes: "bg-[#EEF0EE] text-[#4B525A]", title: day.holiday }
	if (day.day_off) return { label: __("Off"), classes: "bg-[#F6F7F5] text-[#8A9098]", title: __("Day off") }
	if (day.shift)
		return {
			label: day.shift,
			sub: day.location || hours(day.shift),
			classes: shiftClasses(day.shift),
			title: [day.shift, day.location, hours(day.shift)].filter(Boolean).join(" · "),
		}
	return { label: "–", classes: "text-gray-500", title: __("No shift") }
}

// a group per department (A–Z, people without one last)
const departmentGroups = computed(() => {
	const groups = {}
	for (const row of shownRows.value) {
		const key = row.department || ""
		groups[key] ||= { department: key, label: key || __("No department"), rows: [] }
		groups[key].rows.push(row)
	}
	return Object.values(groups).sort((a, b) =>
		!a.department ? 1 : !b.department ? -1 : a.department.localeCompare(b.department)
	)
})
const peopleLabel = (count) => (count == 1 ? __("1 person") : __("{0} people", [count]))

// phones show one day at a time
const dayOf = (row) => row.days[dates.value.indexOf(selectedDate.value)]
</script>

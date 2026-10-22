<template>
	<BaseLayout :pageTitle="__('Attendance')">
		<template #actions>
			<router-link
				:to="{ name: 'EmployeeCheckinListView' }"
				class="text-sm font-semibold text-brand-600 hover:text-brand-700"
			>
				{{ __("Check-in history") }}
			</router-link>
		</template>
		<template #body>
			<div class="flex w-full flex-col gap-5 px-4 pb-24 pt-5 lg:gap-6 lg:px-6">
				<!-- the month in numbers -->
				<div class="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
					<div
						v-for="total in totals"
						:key="total.label"
						class="flex flex-col gap-1.5 rounded-2xl border border-line bg-white px-4 py-3.5 lg:px-5 lg:py-4"
					>
						<div class="flex flex-row items-center gap-2 text-[13px] text-gray-700 lg:text-sm">
							<span :class="['h-2.5 w-2.5 rounded-full', TONE_DOTS[total.tone]]"></span>{{ total.label }}
						</div>
						<div class="text-2xl font-bold leading-none tracking-tight text-ink lg:text-[32px]">{{ total.count }}</div>
						<div class="text-xs text-gray-700 lg:text-[13px]">{{ total.note }}</div>
					</div>
				</div>

				<div class="flex flex-col items-start gap-5 lg:flex-row lg:gap-6">
					<section class="w-full min-w-0 flex-1 rounded-2xl border border-line bg-white p-3.5 lg:p-6">
						<div class="mb-3 flex flex-row items-center justify-between lg:mb-4">
							<button
								type="button"
								class="flex h-10 w-10 items-center justify-center rounded-xl border border-line text-ink hover:bg-gray-50"
								:aria-label="__('Previous month')"
								@click="changeMonth(-1)"
							>
								<FeatherIcon name="chevron-left" class="h-4 w-4" />
							</button>
							<h2 class="text-base font-bold text-ink lg:text-lg">{{ month.format("MMMM YYYY") }}</h2>
							<button
								type="button"
								class="flex h-10 w-10 items-center justify-center rounded-xl border border-line text-ink hover:bg-gray-50"
								:aria-label="__('Next month')"
								@click="changeMonth(1)"
							>
								<FeatherIcon name="chevron-right" class="h-4 w-4" />
							</button>
						</div>
						<div class="grid grid-cols-7 gap-1 lg:gap-1.5">
							<span
								v-for="day in WEEKDAYS"
								:key="day"
								class="py-1.5 text-center text-xs font-semibold text-gray-700"
							>
								{{ day }}
							</span>
							<span v-for="n in offset" :key="`blank-${n}`"></span>
							<button
								v-for="cell in cells"
								:key="cell.date"
								type="button"
								:aria-label="cell.aria"
								:aria-pressed="selectedDate === cell.date"
								:class="[
									'flex h-11 flex-col items-center justify-center rounded-xl border-2 lg:h-[72px] lg:items-start lg:justify-between lg:px-2.5 lg:py-2',
									TONE_CELL[cell.tone],
									selectedDate === cell.date ? '!border-ink' : cell.tone === 'future' ? 'border-line' : 'border-transparent',
								]"
								@click="selectedDate = cell.date"
							>
								<span :class="['text-sm', cell.isToday ? 'font-bold' : 'font-semibold']">{{ cell.day }}</span>
								<span class="hidden text-xs font-semibold lg:block">{{ cell.short }}</span>
							</button>
						</div>
						<div class="mt-4 flex flex-row flex-wrap gap-x-4 gap-y-1.5 text-xs text-gray-700 lg:text-[13px]">
							<span v-for="item in LEGEND" :key="item.label" class="flex flex-row items-center gap-1.5">
								<span :class="['h-2.5 w-2.5 rounded-sm', TONE_DOTS[item.tone]]"></span>{{ item.label }}
							</span>
						</div>
					</section>

					<aside class="flex w-full flex-col gap-5 lg:w-[340px] lg:flex-none lg:gap-6">
						<section v-if="selectedDay" class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 lg:p-6">
							<div class="flex flex-row items-center justify-between gap-2">
								<h2 class="text-base font-bold text-ink lg:text-lg">{{ dayjs(selectedDay.date).format("ddd D MMMM") }}</h2>
								<span :class="['rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[selectedDay.tone === 'future' ? 'neutral' : selectedDay.tone]]">
									{{ selectedDay.label }}
								</span>
							</div>
							<div
								v-for="row in selectedDay.rows"
								:key="row.key"
								class="flex flex-row justify-between gap-3 border-b border-[#EEF0EE] pb-2.5 text-sm last:border-0 last:pb-0"
							>
								<span class="text-gray-700">{{ row.key }}</span>
								<span class="text-right font-semibold text-ink">{{ row.value }}</span>
							</div>
						</section>

						<section class="flex flex-col gap-2.5 rounded-2xl border border-line bg-white p-4 lg:p-6">
							<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("Your schedule") }}</h2>
							<div
								v-for="shift in upcomingShifts"
								:key="shift.name"
								class="flex flex-row justify-between gap-3 text-sm"
							>
								<span class="text-gray-700">{{ shift.shift_dates }}</span>
								<span class="font-semibold text-ink">{{ shift.shift_type }} · {{ shift.shift_timing }}</span>
							</div>
							<div
								v-if="shifts.fetched && !upcomingShifts.length && defaultShift"
								class="flex flex-row justify-between gap-3 text-sm"
							>
								<span class="text-gray-700">{{ __("Every day") }}</span>
								<span class="font-semibold text-ink">{{ defaultShift }}</span>
							</div>
							<div v-else-if="shifts.fetched && !upcomingShifts.length" class="text-sm text-gray-700">
								{{ __("No shift assigned. Ask HR to set one.") }}
							</div>
						</section>

						<section v-if="showAttendanceRequests" class="flex flex-col gap-2 rounded-2xl border border-line bg-white p-4 lg:p-6">
							<router-link :to="{ name: 'AttendanceRequestFormView' }" class="text-sm font-semibold text-brand-600">
								{{ __("Request attendance") }}
							</router-link>
							<router-link :to="{ name: 'ShiftRequestFormView' }" class="text-sm font-semibold text-brand-600">
								{{ __("Request a shift") }}
							</router-link>
						</section>
					</aside>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { getShiftDates, getShiftTiming } from "@/data/attendance"
import { homeData } from "@/data/home"
import { showAttendanceRequests } from "@/utils/navigation"
import { TONE_CLASSES, TONE_DOTS } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const WEEKDAYS = [__("Mon"), __("Tue"), __("Wed"), __("Thu"), __("Fri"), __("Sat"), __("Sun")]
const TONE_CELL = {
	ok: "bg-[#E2F4EA] text-[#0F6B4C]",
	warn: "bg-[#FDEFD6] text-[#8A4B00]",
	bad: "bg-[#FCE6E4] text-[#A8231A]",
	info: "bg-[#E4ECFB] text-[#1E55B8]",
	neutral: "bg-[#F1F3F0] text-gray-600",
	future: "bg-white text-ink",
}
const LEGEND = [
	{ tone: "ok", label: __("Checked in") },
	{ tone: "warn", label: __("Late or half day") },
	{ tone: "info", label: __("On leave") },
	{ tone: "bad", label: __("Absent") },
	{ tone: "neutral", label: __("Day off or no check-in") },
]

const month = ref(dayjs().startOf("month"))
const selectedDate = ref(dayjs().format("YYYY-MM-DD"))
const today = dayjs().format("YYYY-MM-DD")

const monthDays = createResource({ url: "hrms.api.employee_app.get_attendance_month" })
watch(
	month,
	(value) =>
		monthDays.submit({
			from_date: value.format("YYYY-MM-DD"),
			to_date: value.endOf("month").format("YYYY-MM-DD"),
		}),
	{ immediate: true }
)

function changeMonth(step) {
	month.value = month.value.add(step, "month")
	selectedDate.value = month.value.isSame(dayjs(), "month") ? today : month.value.format("YYYY-MM-DD")
}

// one status per day, from attendance first, then the check-in, then the holiday list
function describe(row) {
	const time = row.checked_in_at ? dayjs(row.checked_in_at).format("HH:mm") : ""
	const isDayOff = Boolean(row.holiday)
	if (row.status === "On Leave") return { tone: "info", label: __("On leave"), short: __("Leave") }
	if (row.status === "Absent") return { tone: "bad", label: __("Absent"), short: __("Absent") }
	if (row.status === "Half Day") return { tone: "warn", label: __("Half day"), short: time || __("Half") }
	if (row.status && row.late_entry) return { tone: "warn", label: __("Late"), short: time || __("Late") }
	if (row.status || time) return { tone: "ok", label: __("Checked in"), short: time }
	if (row.date > today) return { tone: "future", label: isDayOff ? row.holiday : __("Upcoming"), short: "" }
	if (isDayOff) return { tone: "neutral", label: row.weekly_off ? __("Day off") : row.holiday, short: row.weekly_off ? "" : __("Holiday") }
	if (row.date === today) return { tone: "future", label: __("Today"), short: __("Today") }
	return { tone: "neutral", label: __("No check-in"), short: "—" }
}

const days = computed(() => (monthDays.data || []).map((row) => ({ ...row, ...describe(row) })))
const offset = computed(() => (month.value.day() + 6) % 7)
const cells = computed(() =>
	days.value.map((row) => ({
		date: row.date,
		day: dayjs(row.date).date(),
		tone: row.tone,
		short: row.short,
		isToday: row.date === today,
		aria: `${dayjs(row.date).format("dddd D MMMM")}, ${row.label}`,
	}))
)

const selectedDay = computed(() => {
	const row = days.value.find((day) => day.date === selectedDate.value)
	if (!row) return null
	const rows = []
	if (row.checked_in_at) rows.push({ key: __("Checked in"), value: dayjs(row.checked_in_at).format("HH:mm") })
	if (row.status) rows.push({ key: __("Attendance"), value: __(row.status) })
	if (row.leave_type) rows.push({ key: __("Leave type"), value: row.leave_type })
	if (row.shift) rows.push({ key: __("Shift"), value: row.shift })
	if (row.holiday && !row.weekly_off) rows.push({ key: __("Holiday"), value: row.holiday })
	if (!rows.length) rows.push({ key: __("Record"), value: row.date > today ? __("Nothing yet") : __("None") })
	return { ...row, rows }
})

const totals = computed(() => {
	const past = days.value.filter((row) => row.date <= today)
	const count = (test) => past.filter(test).length
	return [
		{ label: __("On time"), tone: "ok", count: count((row) => row.tone === "ok"), note: __("days this month") },
		{ label: __("Late"), tone: "warn", count: count((row) => row.tone === "warn"), note: __("late or half day") },
		{ label: __("On leave"), tone: "info", count: count((row) => row.tone === "info"), note: __("days") },
		{ label: __("Absent"), tone: "bad", count: count((row) => row.tone === "bad"), note: __("marked absent") },
	]
})

const shifts = createResource({
	url: "hrms.api.get_shifts",
	auto: true,
	cache: "hrms:shifts",
	transform: (data) =>
		data.map((assignment) => ({
			...assignment,
			is_upcoming: !assignment.end_date || dayjs(assignment.end_date).isAfter(dayjs()),
			shift_dates: getShiftDates(assignment),
			shift_timing: getShiftTiming(assignment),
		})),
})
const upcomingShifts = computed(() => (shifts.data || []).filter((shift) => shift.is_upcoming).slice(0, 4))

// without shift assignments the employee's default shift applies
if (!homeData.data) homeData.reload()
const defaultShift = computed(() => {
	const me = homeData.data?.me
	if (!me?.shift) return ""
	const times = me.shift_start && me.shift_end ? ` · ${dayjs(me.shift_start).format("HH:mm")} – ${dayjs(me.shift_end).format("HH:mm")}` : ""
	return `${me.shift}${times}`
})
</script>

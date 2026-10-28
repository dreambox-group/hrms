<template>
	<div class="flex flex-col gap-6 p-5 lg:p-6">
		<template v-if="!sent">
			<p class="text-sm leading-relaxed text-gray-700">
				{{ __("Worked on a holiday or a day off? Pick the days. Once your supervisors approve, you get the same number of days off (Cuti Pengganti), each usable until {0} months after the day you worked.", [months]) }}
			</p>

			<!-- 1. the days worked -->
			<div class="flex flex-col gap-3">
				<div class="text-sm font-semibold text-ink">{{ __("1. Which holidays did you work?") }}</div>
				<div class="rounded-2xl border border-line p-3 lg:p-4">
					<div class="mb-2 flex flex-row items-center justify-between">
						<button
							type="button"
							class="flex h-10 w-10 items-center justify-center rounded-xl border border-line text-ink hover:bg-gray-50 disabled:opacity-40"
							:aria-label="__('Previous month')"
							:disabled="!month.isAfter(dayjs().subtract(months, 'month'), 'month')"
							@click="month = month.subtract(1, 'month')"
						>
							<FeatherIcon name="chevron-left" class="h-4 w-4" />
						</button>
						<span class="text-[15px] font-semibold text-ink">{{ month.format("MMMM YYYY") }}</span>
						<button
							type="button"
							class="flex h-10 w-10 items-center justify-center rounded-xl border border-line text-ink hover:bg-gray-50 disabled:opacity-40"
							:aria-label="__('Next month')"
							:disabled="month.isSame(dayjs(), 'month')"
							@click="month = month.add(1, 'month')"
						>
							<FeatherIcon name="chevron-right" class="h-4 w-4" />
						</button>
					</div>
					<div class="grid grid-cols-7 gap-1 text-center">
						<span v-for="day in WEEKDAYS" :key="day" class="py-1 text-xs font-semibold text-gray-700">{{ day }}</span>
						<span v-for="n in offset" :key="`blank-${n}`"></span>
						<button
							v-for="cell in cells"
							:key="cell.date"
							type="button"
							:disabled="cell.disabled"
							:aria-pressed="picked.includes(cell.date)"
							:aria-label="cell.aria"
							:title="cell.holiday"
							:class="[
								'h-11 rounded-xl text-sm',
								picked.includes(cell.date)
									? 'bg-brand-600 font-bold text-white'
									: cell.disabled
										? 'text-gray-400'
										: 'bg-[#EEF0EE] font-semibold text-ink hover:bg-gray-200',
							]"
							@click="toggle(cell.date)"
						>
							{{ cell.day }}
						</button>
					</div>
					<p class="mt-2 text-xs text-gray-700">
						{{ holidays.loading ? __("Loading your holidays…") : __("Only your holidays and days off can be picked.") }}
					</p>
				</div>
				<div v-if="picked.length" class="rounded-xl bg-[#E4ECFB] px-3.5 py-2.5 text-[13px] leading-snug text-[#1E55B8]">
					<div class="font-semibold">
						{{ picked.length == 1 ? __("If approved: 1 day off") : __("If approved: {0} days off", [picked.length]) }}
					</div>
					<div v-for="date in picked" :key="date">
						{{ __("{0}: usable until {1}", [dayjs(date).format("ddd D MMM"), dayjs(date).add(months, "month").format("D MMM YYYY")]) }}
					</div>
				</div>
			</div>

			<!-- 2. what for -->
			<div class="flex flex-col gap-2">
				<label for="cuti-reason" class="text-sm font-semibold text-ink">{{ __("2. What was the work?") }}</label>
				<textarea
					id="cuti-reason"
					v-model="reason"
					rows="3"
					:placeholder="__('e.g. Event setup on Saturday and Sunday for client X')"
					class="rounded-xl border border-[#D5DAD4] px-3.5 py-3 text-[15px] text-ink focus:border-brand-600 focus:ring-brand-600"
				></textarea>
			</div>

			<div v-if="error" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
				{{ error }}
			</div>

			<button
				type="button"
				class="flex min-h-[52px] w-full items-center justify-center rounded-xl bg-brand-600 text-base font-semibold text-white hover:bg-brand-700 disabled:bg-gray-300 disabled:text-gray-600"
				:disabled="!picked.length || !reason.trim() || submit.loading"
				@click="send"
			>
				{{ submit.loading ? __("Sending…") : __("Send to my supervisors") }}
			</button>
		</template>

		<div v-else class="flex flex-col items-center gap-3 py-6 text-center">
			<span class="flex h-12 w-12 items-center justify-center rounded-full bg-[#E2F4EA] text-[#0F6B4C]">
				<FeatherIcon name="check" class="h-6 w-6" />
			</span>
			<h2 class="text-xl font-bold text-ink">{{ __("Sent") }}</h2>
			<p class="text-sm text-gray-700">{{ __("Your supervisors will see each day on their Home page. You'll see their decisions here.") }}</p>
			<button
				type="button"
				class="mt-2 min-h-[48px] rounded-xl border border-line px-6 text-[15px] font-semibold text-ink hover:bg-gray-50"
				@click="emit('close')"
			>
				{{ __("Done") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const props = defineProps({ months: { type: Number, default: 3 } })
const emit = defineEmits(["close", "sent"])

const WEEKDAYS = [__("Mon"), __("Tue"), __("Wed"), __("Thu"), __("Fri"), __("Sat"), __("Sun")].map((day) => day[0])
const month = ref(dayjs().startOf("month"))
const picked = ref([])
const reason = ref("")
const sent = ref(false)
const error = ref("")

// the employee's holidays (public holidays and weekly days off) in the shown month
const holidays = createResource({
	url: "hrms.api.employee_app.get_my_holidays",
	makeParams: () => ({
		from_date: month.value.format("YYYY-MM-DD"),
		to_date: month.value.endOf("month").format("YYYY-MM-DD"),
	}),
	auto: true,
	cache: false,
})
const holidayByDate = computed(() => Object.fromEntries((holidays.data || []).map((row) => [row.date, row])))
watch(month, () => holidays.reload())

const offset = computed(() => (month.value.day() + 6) % 7)
// only holidays can be picked; not future days, nor days whose days off would already have expired
const cells = computed(() => {
	const today = dayjs()
	const oldest = today.subtract(props.months, "month")
	return Array.from({ length: month.value.daysInMonth() }, (_, i) => {
		const date = month.value.date(i + 1)
		const key = date.format("YYYY-MM-DD")
		const holiday = holidayByDate.value[key]
		const description = holiday && (holiday.description || (holiday.weekly_off ? __("Day off") : __("Holiday")))
		return {
			date: key,
			day: i + 1,
			holiday: description,
			aria: [date.format("dddd D MMMM YYYY"), description].filter(Boolean).join(", "),
			disabled: !holiday || date.isAfter(today, "day") || date.isBefore(oldest, "day"),
		}
	})
})

function toggle(date) {
	picked.value = picked.value.includes(date)
		? picked.value.filter((d) => d !== date)
		: [...picked.value, date].sort()
}

const submit = createResource({ url: "hrms.api.employee_app.request_cuti_pengganti" })
function send() {
	error.value = ""
	submit.submit(
		{ work_dates: picked.value, reason: reason.value },
		{
			onSuccess() {
				sent.value = true
				emit("sent")
			},
			onError(err) {
				error.value = err.messages?.[0] || __("The request could not be sent.")
			},
		}
	)
}
</script>

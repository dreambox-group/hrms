<template>
	<div class="flex flex-col gap-5 rounded-2xl border border-line p-4">
		<div class="flex flex-row items-start justify-between gap-3">
			<h3 class="text-base font-bold text-ink">{{ __("Change or cancel this leave") }}</h3>
			<button
				type="button"
				class="flex h-9 w-9 flex-none items-center justify-center rounded-xl bg-gray-100 text-ink"
				:aria-label="__('Close')"
				@click="emit('close')"
			>
				<FeatherIcon name="x" class="h-4 w-4" />
			</button>
		</div>

		<!-- 1. what should happen -->
		<fieldset class="flex flex-col gap-2">
			<legend class="mb-2 text-sm font-semibold text-ink">{{ __("1. What do you need?") }}</legend>
			<label
				v-for="option in OPTIONS"
				:key="option.value"
				:class="[
					'flex cursor-pointer flex-row items-start gap-3 rounded-xl border p-3.5',
					change === option.value ? 'border-brand-600 bg-brand-50' : 'border-line hover:border-gray-400',
				]"
			>
				<input v-model="change" type="radio" name="leave-change" :value="option.value" class="mt-0.5 text-brand-600 focus:ring-brand-600" />
				<span class="flex flex-col">
					<span class="text-[15px] font-semibold text-ink">{{ option.label }}</span>
					<span class="text-[13px] text-gray-700">{{ option.hint }}</span>
				</span>
			</label>
		</fieldset>

		<!-- 2. the new dates -->
		<div v-if="change === CHANGE" class="flex flex-col gap-2">
			<div class="text-sm font-semibold text-ink">{{ __("2. Pick the new dates") }}</div>
			<div class="text-[13px] text-gray-700">
				{{ fixedRule ? __("Tap the first day; the end date is set for you.") : __("Tap the first day, then the last.") }}
			</div>
			<div class="rounded-2xl border border-line p-3">
				<div class="mb-2 flex flex-row items-center justify-between">
					<button
						type="button"
						class="flex h-10 w-10 items-center justify-center rounded-xl border border-line text-ink hover:bg-gray-50"
						:aria-label="__('Previous month')"
						@click="month = month.subtract(1, 'month')"
					>
						<FeatherIcon name="chevron-left" class="h-4 w-4" />
					</button>
					<span class="text-[15px] font-semibold text-ink">{{ month.format("MMMM YYYY") }}</span>
					<button
						type="button"
						class="flex h-10 w-10 items-center justify-center rounded-xl border border-line text-ink hover:bg-gray-50"
						:aria-label="__('Next month')"
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
						:aria-pressed="cell.inRange"
						:aria-label="cell.aria"
						:class="[
							'h-10 rounded-xl text-sm',
							cell.edge ? 'bg-brand-600 font-bold text-white' : cell.inRange ? 'bg-brand-50 font-semibold text-brand-800' : 'font-semibold text-ink hover:bg-gray-100',
						]"
						@click="pick(cell.date)"
					>
						{{ cell.day }}
					</button>
				</div>
			</div>
			<div v-if="newFrom" class="rounded-xl bg-[#E4ECFB] px-3.5 py-2.5 text-[13px] leading-snug text-[#1E55B8]">
				{{ __("Now: {0}. New: {1}.", [range(doc.from_date, doc.to_date), range(newFrom, newTo || newFrom)]) }}
			</div>
		</div>

		<!-- 3. why -->
		<div class="flex flex-col gap-2">
			<label for="leave-change-reason" class="text-sm font-semibold text-ink">
				{{ change === CHANGE ? __("3. Why?") : __("2. Why?") }}
			</label>
			<textarea
				id="leave-change-reason"
				v-model="reason"
				rows="3"
				:placeholder="__('e.g. The family event moved to the next week')"
				class="rounded-xl border border-[#D5DAD4] px-3.5 py-3 text-[15px] text-ink focus:border-brand-600 focus:ring-brand-600"
			></textarea>
		</div>

		<!-- the checklist: talk to HR before sending -->
		<fieldset class="flex flex-col gap-2 rounded-xl bg-[#FDEFD6] p-3.5">
			<legend class="sr-only">{{ __("Before you send") }}</legend>
			<div class="text-sm font-semibold text-[#8A4B00]">{{ __("Before you send") }}</div>
			<label class="flex cursor-pointer flex-row items-start gap-3 text-sm text-ink">
				<input v-model="informedHr" type="checkbox" class="mt-0.5 h-5 w-5 rounded text-brand-600 focus:ring-brand-600" />
				<span>{{ __("I have already told HR about this change (chat or in person)") }}</span>
			</label>
			<label class="flex cursor-pointer flex-row items-start gap-3 text-sm text-ink">
				<input v-model="understands" type="checkbox" class="mt-0.5 h-5 w-5 rounded text-brand-600 focus:ring-brand-600" />
				<span>{{ __("I understand my leave stays as it is until HR approves this request") }}</span>
			</label>
		</fieldset>

		<div v-if="error" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{{ error }}</div>

		<button
			type="button"
			class="flex min-h-[48px] w-full items-center justify-center rounded-xl bg-brand-600 text-[15px] font-semibold text-white hover:bg-brand-700 disabled:bg-gray-300 disabled:text-gray-600"
			:disabled="!ready || submit.loading"
			@click="send"
		>
			{{ submit.loading ? __("Sending…") : __("Send to HR") }}
		</button>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"

import { settings } from "@/data/settings"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const props = defineProps({ doc: { type: Object, required: true } })
const emit = defineEmits(["close", "sent"])

const CANCEL = "Cancel the leave"
const CHANGE = "Change the dates"
const OPTIONS = [
	{ value: CANCEL, label: __("Cancel the leave"), hint: __("The leave is removed once HR approves.") },
	{ value: CHANGE, label: __("Change the dates"), hint: __("Your approval stays; only the dates move.") },
]
const WEEKDAYS = [__("Mon"), __("Tue"), __("Wed"), __("Thu"), __("Fri"), __("Sat"), __("Sun")].map((day) => day[0])

const change = ref("")
const reason = ref("")
const informedHr = ref(false)
const understands = ref(false)
const newFrom = ref("")
const newTo = ref("")
const error = ref("")
const month = ref(dayjs(props.doc.from_date).startOf("month"))

const fixedRule = computed(() =>
	(settings.data?.leave_types_with_fixed_length || []).find((row) => row.leave_type === props.doc.leave_type)
)

const offset = computed(() => (month.value.day() + 6) % 7)
const cells = computed(() => {
	const end = newTo.value || newFrom.value
	return Array.from({ length: month.value.daysInMonth() }, (_, i) => {
		const date = month.value.date(i + 1).format("YYYY-MM-DD")
		return {
			date,
			day: i + 1,
			aria: dayjs(date).format("dddd D MMMM YYYY"),
			edge: date === newFrom.value || date === end,
			inRange: Boolean(newFrom.value) && date >= newFrom.value && date <= end,
		}
	})
})

const fixedEnd = createResource({ url: "hrms.api.employee_app.get_fixed_leave_end" })
function pick(date) {
	if (fixedRule.value) {
		newFrom.value = date
		newTo.value = ""
		fixedEnd.submit(
			{ leave_type: props.doc.leave_type, from_date: date },
			{ onSuccess: (end) => (newTo.value = end || date) }
		)
	} else if (!newFrom.value || newTo.value) {
		newFrom.value = date
		newTo.value = ""
	} else if (date < newFrom.value) {
		newTo.value = newFrom.value
		newFrom.value = date
	} else {
		newTo.value = date
	}
}

const range = (from, to) => {
	const start = dayjs(from).format("ddd D MMM")
	return from === to ? start : `${start} – ${dayjs(to).format("ddd D MMM")}`
}

const ready = computed(
	() =>
		Boolean(change.value) &&
		(change.value === CANCEL || Boolean(newFrom.value)) &&
		Boolean(reason.value.trim()) &&
		informedHr.value &&
		understands.value
)
watch(change, () => (error.value = ""))

const submit = createResource({ url: "hrms.api.employee_app.request_leave_change" })
function send() {
	error.value = ""
	submit.submit(
		{
			leave_application: props.doc.name,
			change: change.value,
			reason: reason.value,
			informed_hr: informedHr.value ? 1 : 0,
			understands_waiting: understands.value ? 1 : 0,
			new_from_date: change.value === CHANGE ? newFrom.value : null,
			new_to_date: change.value === CHANGE ? newTo.value || newFrom.value : null,
		},
		{
			onSuccess: () => emit("sent"),
			onError(err) {
				error.value = err.messages?.[0] || __("The request could not be sent.")
			},
		}
	)
}
</script>

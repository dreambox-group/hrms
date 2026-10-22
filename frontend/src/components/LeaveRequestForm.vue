<template>
	<div class="flex h-full min-h-0 flex-col bg-white">
		<template v-if="!sent">
			<div class="flex min-h-0 flex-1 flex-col gap-7 overflow-y-auto p-5 lg:p-6">
				<!-- 1. type -->
				<fieldset class="flex flex-col gap-2.5">
					<legend class="mb-2.5 text-sm font-semibold text-ink">{{ __("1. What kind of leave?") }}</legend>
					<div v-if="leaveTypes.loading && !typeCards.length" class="text-sm text-gray-700">
						{{ __("Loading…") }}
					</div>
					<button
						v-for="card in typeCards"
						:key="card.name"
						type="button"
						:aria-pressed="form.leave_type === card.name"
						:class="[
							'flex items-center gap-3.5 rounded-xl border-2 px-4 py-3.5 text-left',
							form.leave_type === card.name ? 'border-brand-600 bg-brand-50' : 'border-line bg-white hover:border-gray-400',
						]"
						@click="form.leave_type = card.name"
					>
						<span
							:class="[
								'flex h-5 w-5 flex-none items-center justify-center rounded-full border-2',
								form.leave_type === card.name ? 'border-brand-600' : 'border-[#B9C0BA]',
							]"
						>
							<span v-if="form.leave_type === card.name" class="h-2.5 w-2.5 rounded-full bg-brand-600"></span>
						</span>
						<span class="flex flex-1 flex-col gap-0.5">
							<span class="text-[15px] font-semibold text-ink">{{ card.name }}</span>
							<span class="text-[13px] text-gray-700">{{ card.hint }}</span>
						</span>
						<span v-if="card.side" class="text-[15px] font-bold text-ink">{{ card.side }}</span>
					</button>
					<div v-if="leaveTypes.fetched && !typeCards.length" class="text-sm text-gray-700">
						{{ __("No leave types are available to you. Ask HR.") }}
					</div>
				</fieldset>

				<!-- 2. dates -->
				<div class="flex flex-col gap-3">
					<div class="text-sm font-semibold text-ink">
						{{ __("2. Which days?") }}
						<span class="font-normal text-gray-700">{{ __("Tap the first day, then the last.") }}</span>
					</div>
					<div class="rounded-2xl border border-line p-3 lg:p-4">
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
								:aria-label="cell.aria"
								:class="['relative h-11 text-sm', cell.classes]"
								@click="pick(cell.date)"
							>
								{{ cell.day }}
								<span
									v-if="cell.holiday"
									class="absolute bottom-1.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-[#A8231A]"
								></span>
							</button>
						</div>
						<div v-if="monthHolidays.length" class="mt-2.5 flex flex-col gap-1 text-xs text-gray-700">
							<div v-for="holiday in monthHolidays" :key="holiday.date" class="flex flex-row items-center gap-1.5">
								<span class="h-1.5 w-1.5 rounded-full bg-[#A8231A]"></span>
								{{ dayjs(holiday.date).format("ddd D MMM") }} · {{ holiday.holiday }}
							</div>
						</div>
					</div>
					<label v-if="isSingleDay" class="flex min-h-[44px] flex-row items-center gap-2.5 text-sm text-ink">
						<input v-model="form.half_day" type="checkbox" class="h-[18px] w-[18px] rounded accent-brand-600" />
						{{ __("Half day only") }}
					</label>
				</div>

				<!-- summary -->
				<div v-if="form.from_date" role="status" :class="['flex flex-col gap-1 rounded-2xl p-4', summary.box]">
					<div class="text-base font-bold text-ink">{{ summary.line1 }}</div>
					<div :class="['text-sm', summary.text]">{{ summary.line2 }}</div>
				</div>

				<!-- 3. note -->
				<div class="flex flex-col gap-2">
					<label for="leave-reason" class="text-sm font-semibold text-ink">
						{{ __("3. Note for your approver") }}
						<span class="font-normal text-gray-700">{{ __("(optional)") }}</span>
					</label>
					<textarea
						id="leave-reason"
						v-model="form.description"
						rows="3"
						:placeholder="__('e.g. Family event in Bandung')"
						class="rounded-xl border border-[#D5DAD4] px-3.5 py-3 text-[15px] text-ink focus:border-brand-600 focus:ring-brand-600"
					></textarea>
				</div>

				<!-- document -->
				<div class="flex flex-col gap-2">
					<span class="text-sm font-semibold text-ink">
						{{ __("Supporting document") }}
						<span class="font-normal text-gray-700">{{ __("(optional, can be added later)") }}</span>
					</span>
					<label
						class="flex cursor-pointer flex-row items-center justify-center gap-2 rounded-xl border border-dashed border-[#D5DAD4] px-3 py-3 text-sm font-medium text-ink hover:bg-gray-50"
					>
						<FeatherIcon :name="file ? 'file-text' : 'upload'" class="h-4 w-4" />
						{{ file ? file.name : __("Add a photo or PDF") }}
						<input type="file" class="hidden" accept="image/*,application/pdf" @change="pickFile" />
					</label>
				</div>

				<!-- approver -->
				<div class="flex flex-row items-center gap-3 rounded-xl bg-page px-4 py-3.5">
					<span
						class="flex h-9 w-9 flex-none items-center justify-center rounded-full text-[13px] font-semibold text-ink"
						:style="{ background: avatarColour(approverLabel) }"
					>
						{{ initials(approverLabel) || "?" }}
					</span>
					<div class="flex min-w-0 flex-1 flex-col text-sm leading-snug">
						<span class="text-gray-700">{{ __("Goes to") }}</span>
						<select
							v-if="approverChoices.length > 1"
							v-model="form.leave_approver"
							class="mt-1 rounded-lg border-[#D5DAD4] py-1.5 text-sm font-semibold text-ink"
						>
							<option v-for="choice in approverChoices" :key="choice.name" :value="choice.name">
								{{ choice.full_name || choice.name }}
							</option>
						</select>
						<strong v-else class="font-semibold text-ink">{{ approverLabel || __("Your Leave Approver") }}</strong>
					</div>
				</div>

				<div v-if="errors.length" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
					<div v-for="message in errors" :key="message" v-html="message"></div>
				</div>
			</div>

			<div class="flex flex-row gap-3 border-t border-[#EEF0EE] px-5 py-4 lg:px-6">
				<button
					type="button"
					class="min-h-[52px] rounded-xl border border-line px-5 text-[15px] font-semibold text-ink hover:bg-gray-50"
					@click="emit('close')"
				>
					{{ __("Cancel") }}
				</button>
				<button
					type="button"
					class="min-h-[52px] flex-1 rounded-xl bg-brand-600 text-base font-semibold text-white hover:bg-brand-700 disabled:bg-gray-200 disabled:text-gray-600"
					:disabled="!canSend || sending"
					@click="send"
				>
					{{ sending ? __("Sending…") : __("Send request") }}
				</button>
			</div>
		</template>

		<!-- sent -->
		<div v-else class="flex flex-1 flex-col items-center gap-4 px-6 py-12 text-center">
			<span class="flex h-16 w-16 items-center justify-center rounded-full bg-[#E2F4EA] text-[#0F6B4C]">
				<FeatherIcon name="check" class="h-8 w-8" />
			</span>
			<h2 class="text-2xl font-bold text-ink">
				{{ sentTo ? __("Request sent to {0}", [sentTo]) : __("Request sent") }}
			</h2>
			<p class="max-w-[340px] text-[15px] leading-relaxed text-gray-700">
				{{ __("You will see the decision on your Home page.") }}
			</p>
			<div class="flex w-full max-w-[360px] flex-row items-center justify-between rounded-2xl border border-line p-4 text-left">
				<div>
					<div class="text-[15px] font-semibold text-ink">{{ sent.leave_type }}</div>
					<div class="mt-0.5 text-[13px] text-gray-700">{{ sent.dates }}</div>
				</div>
				<span :class="['rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES.warn]">{{ __("Waiting") }}</span>
			</div>
			<div class="mt-2 flex flex-row gap-3">
				<button
					type="button"
					class="min-h-[48px] rounded-xl border border-line px-5 text-[15px] font-semibold text-ink hover:bg-gray-50"
					@click="reset"
				>
					{{ __("Request another") }}
				</button>
				<button
					type="button"
					class="min-h-[48px] rounded-xl bg-brand-600 px-6 text-[15px] font-semibold text-white hover:bg-brand-700"
					@click="emit('close')"
				>
					{{ __("Done") }}
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"

import { homeData, leaveDocumentUpload } from "@/data/home"
import { availableLeaves, leaveBalance, myLeaves } from "@/data/leaves"
import { TONE_CLASSES, avatarColour, initials } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")
const emit = defineEmits(["close"])

const WEEKDAYS = [__("Mon"), __("Tue"), __("Wed"), __("Thu"), __("Fri"), __("Sat"), __("Sun")].map((day) => day[0])

const blank = () => ({ leave_type: "", from_date: "", to_date: "", half_day: false, description: "", leave_approver: "" })
const form = reactive(blank())
const file = ref(null)
const errors = ref([])
const sent = ref(null)
const sentTo = ref("")
const month = ref(dayjs().startOf("month"))
const calendarDays = reactive({}) // date → { holiday, weekly_off }

// leave types the employee can use today: allocated ones and the unpaid (LWP) ones
const leaveTypes = createResource({
	url: "hrms.api.get_leave_types",
	params: { employee: employee.data.name, date: dayjs().format("YYYY-MM-DD") },
	auto: true,
})
leaveBalance.reload()

const typeCards = computed(() =>
	(leaveTypes.data || []).map((name) => {
		const balance = leaveBalance.data?.[name]
		if (!balance) return { name, hint: __("Unpaid · deducted from salary"), side: "" }
		return {
			name,
			hint: __("Paid · from your {0} days", [balance.allocated_leaves]),
			side: __("{0} left", [availableLeaves(balance)]),
			left: availableLeaves(balance),
		}
	})
)
const selectedType = computed(() => typeCards.value.find((card) => card.name === form.leave_type))

// who decides
const approval = createResource({
	url: "hrms.api.get_leave_approval_details",
	params: { employee: employee.data.name },
	auto: true,
	onSuccess(data) {
		if (!data.approval_by_levels && !form.leave_approver) form.leave_approver = data.leave_approver || ""
	},
})
const approverChoices = computed(() =>
	approval.data && !approval.data.approval_by_levels ? approval.data.department_approvers || [] : []
)
const approverLabel = computed(() => {
	const data = approval.data
	if (!data) return ""
	if (data.approval_by_levels) {
		const names = (data.department_approvers || []).map((row) => row.full_name || row.name)
		return names.length ? names.slice(0, 2).join(", ") + (names.length > 2 ? ` +${names.length - 2}` : "") : ""
	}
	const chosen = approverChoices.value.find((row) => row.name === form.leave_approver)
	return chosen?.full_name || data.leave_approver_name || form.leave_approver || ""
})

// the month shown, with its holidays and days off
const monthDays = createResource({
	url: "hrms.api.employee_app.get_attendance_month",
	onSuccess(rows) {
		for (const row of rows) calendarDays[row.date] = { holiday: row.holiday, weekly_off: row.weekly_off }
	},
})
watch(
	month,
	(value) =>
		monthDays.submit({
			from_date: value.format("YYYY-MM-DD"),
			to_date: value.endOf("month").format("YYYY-MM-DD"),
		}),
	{ immediate: true }
)

const offset = computed(() => (month.value.day() + 6) % 7)
const isOff = (date) => Boolean(calendarDays[date]?.holiday)
const cells = computed(() => {
	const list = []
	const start = form.from_date
	const end = form.to_date || form.from_date
	for (let d = 1; d <= month.value.daysInMonth(); d++) {
		const date = month.value.date(d).format("YYYY-MM-DD")
		const info = calendarDays[date] || {}
		const edge = date === start || date === end
		const inRange = start && date >= start && date <= end
		const off = isOff(date)
		list.push({
			date,
			day: d,
			holiday: Boolean(info.holiday && !info.weekly_off),
			aria: `${dayjs(date).format("dddd D MMMM")}${info.holiday ? `, ${info.holiday}` : ""}`,
			classes: edge
				? "rounded-xl bg-brand-600 font-bold text-white"
				: inRange
					? `rounded bg-brand-100 font-medium ${off ? "text-gray-600" : "text-ink"}`
					: `rounded-xl font-medium hover:bg-gray-100 ${off ? "text-gray-500" : "text-ink"}`,
		})
	}
	return list
})
const monthHolidays = computed(() =>
	Object.entries(calendarDays)
		.filter(([date, info]) => info.holiday && !info.weekly_off && dayjs(date).isSame(month.value, "month"))
		.map(([date, info]) => ({ date, holiday: info.holiday }))
		.sort((a, b) => (a.date < b.date ? -1 : 1))
)

function pick(date) {
	if (!form.from_date || form.to_date) {
		form.from_date = date
		form.to_date = ""
		form.half_day = false
	} else if (date < form.from_date) {
		form.to_date = form.from_date
		form.from_date = date
	} else {
		form.to_date = date
	}
}

const toDate = computed(() => form.to_date || form.from_date)

// working days in the range before a type is chosen; the server's count once it is
const localDays = computed(() => {
	if (!form.from_date) return 0
	let count = 0
	for (let d = dayjs(form.from_date); !d.isAfter(toDate.value, "day"); d = d.add(1, "day")) {
		if (!isOff(d.format("YYYY-MM-DD"))) count++
	}
	return count
})
const isSingleDay = computed(() => Boolean(form.from_date) && form.from_date === toDate.value && localDays.value === 1)

const leaveDays = createResource({
	url: "hrms.hr.doctype.leave_application.leave_application.get_number_of_leave_days",
})
watch(
	() => [form.leave_type, form.from_date, toDate.value, form.half_day],
	() => {
		if (!(form.leave_type && form.from_date)) return
		leaveDays.submit({
			employee: employee.data.name,
			leave_type: form.leave_type,
			from_date: form.from_date,
			to_date: toDate.value,
			half_day: form.half_day ? 1 : 0,
			half_day_date: form.half_day ? form.from_date : null,
		})
	}
)
const days = computed(() => {
	if (form.leave_type && leaveDays.data != null && !leaveDays.loading) return Number(leaveDays.data)
	return form.half_day ? 0.5 : localDays.value
})

const rangeLabel = computed(() => {
	if (!form.from_date) return ""
	const start = dayjs(form.from_date).format("ddd D MMM")
	return form.from_date === toDate.value ? start : `${start} – ${dayjs(toDate.value).format("ddd D MMM")}`
})
const daysLabel = (n) => (n === 0.5 ? __("half a day") : n === 1 ? __("1 day") : __("{0} days", [n]))

const summary = computed(() => {
	const line1 = `${rangeLabel.value} · ${daysLabel(days.value)}`
	const grey = { box: "bg-page", text: "text-gray-700" }
	const amber = { box: "bg-[#FDEFD6]", text: "text-[#8A4B00]" }
	const green = { box: "bg-[#E2F4EA]", text: "text-[#0F6B4C]" }
	if (!days.value) return { ...grey, line1, line2: __("Only weekend or holiday days, so nothing is counted.") }
	if (!selectedType.value) return { ...grey, line1, line2: __("Choose a leave type to see your balance.") }
	if (selectedType.value.left == null)
		return { ...amber, line1, line2: __("{0} will be deducted from your salary.", [daysLabel(days.value)]) }
	const left = selectedType.value.left
	if (days.value > left)
		return {
			...amber,
			line1,
			line2: __("Only {0} days of {1} left. Ask HR, or use unpaid leave for the rest.", [left, form.leave_type]),
		}
	return { ...green, line1, line2: __("{0} days of {1} left after this.", [left - days.value, form.leave_type]) }
})

const canSend = computed(() => Boolean(form.leave_type && form.from_date && days.value > 0))
const insert = createResource({ url: "frappe.client.insert" })
const sending = computed(() => insert.loading || leaveDocumentUpload.loading)

function pickFile(event) {
	file.value = event.target.files?.[0] || null
	event.target.value = ""
}

function send() {
	errors.value = []
	const doc = {
		doctype: "Leave Application",
		employee: employee.data.name,
		leave_type: form.leave_type,
		from_date: form.from_date,
		to_date: toDate.value,
		half_day: form.half_day ? 1 : 0,
		half_day_date: form.half_day ? form.from_date : null,
		description: form.description,
		posting_date: dayjs().format("YYYY-MM-DD"),
		status: "Open",
	}
	if (approval.data && !approval.data.approval_by_levels && form.leave_approver) doc.leave_approver = form.leave_approver

	insert.submit(
		{ doc },
		{
			onSuccess(saved) {
				const finish = () => {
					sentTo.value = approverLabel.value
					sent.value = { leave_type: saved.leave_type, dates: `${rangeLabel.value} · ${daysLabel(saved.total_leave_days)}` }
					myLeaves.reload()
					leaveBalance.reload()
					homeData.reload()
				}
				if (!file.value) return finish()
				const reader = new FileReader()
				reader.onload = () =>
					leaveDocumentUpload.submit(
						{ leave_application: saved.name, filename: file.value.name, content: reader.result },
						{
							onSuccess: finish,
							onError(error) {
								finish()
								errors.value = [__("The request was sent, but the document could not be added: {0}", [error.messages?.[0] || ""])]
							},
						}
					)
				reader.readAsDataURL(file.value)
			},
			onError(error) {
				errors.value = error.messages?.length ? error.messages : [__("The request could not be sent.")]
			},
		}
	)
}

function reset() {
	Object.assign(form, blank())
	if (approval.data && !approval.data.approval_by_levels) form.leave_approver = approval.data.leave_approver || ""
	file.value = null
	errors.value = []
	sent.value = null
}
</script>

<template>
	<BaseLayout :pageTitle="slip ? slipPeriod(slip) : __('Salary slip')" :backTo="{ name: 'SalarySlipsDashboard' }" :backLabel="__('Salary')">
		<template #actions>
			<button
				v-if="slip"
				type="button"
				class="min-h-[44px] rounded-xl bg-brand-600 px-5 text-[15px] font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
				:disabled="downloading"
				@click="download"
			>
				{{ downloading ? __("Downloading…") : __("Download PDF") }}
			</button>
		</template>
		<template #body>
			<div class="flex w-full flex-col gap-5 px-4 pb-24 pt-5 lg:gap-6 lg:px-6">
				<div v-if="downloadError" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
					{{ downloadError }}
				</div>
				<div v-if="resource.error" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
					{{ __("This salary slip could not be opened.") }}
				</div>

				<template v-if="slip">
					<!-- take-home pay -->
					<section class="grid grid-cols-1 gap-4 md:grid-cols-3">
						<div class="flex flex-col gap-1.5 rounded-2xl border border-line bg-white p-5 md:col-span-1">
							<span class="text-sm text-gray-700">{{ __("Take-home pay") }}</span>
							<span class="text-[32px] font-bold leading-none tracking-tight text-ink">{{ money(slip.rounded_total || slip.net_pay) }}</span>
							<span class="text-[13px] text-gray-700">{{ slip.employee_name }} · {{ slip.designation || slip.company }}</span>
						</div>
						<div class="flex flex-col gap-1.5 rounded-2xl border border-line bg-white p-5">
							<span class="text-sm text-gray-700">{{ __("Gross pay") }}</span>
							<span class="text-2xl font-bold text-ink">{{ money(slip.gross_pay) }}</span>
						</div>
						<div class="flex flex-col gap-1.5 rounded-2xl border border-line bg-white p-5">
							<span class="text-sm text-gray-700">{{ __("Deductions") }}</span>
							<span class="text-2xl font-bold text-ink">{{ money(slip.total_deduction) }}</span>
						</div>
					</section>

					<div class="flex flex-col items-start gap-5 lg:flex-row lg:gap-6">
						<section class="flex w-full min-w-0 flex-1 flex-col gap-1 rounded-2xl border border-line bg-white p-4 lg:p-6">
							<h2 class="pb-2 text-base font-bold text-ink lg:text-lg">{{ __("Earnings") }}</h2>
							<div v-for="row in slip.earnings" :key="row.name" class="flex flex-row justify-between gap-3 border-t border-[#EEF0EE] py-2.5 text-sm">
								<span class="text-ink">{{ row.salary_component }}</span>
								<span class="font-semibold text-ink">{{ money(row.amount) }}</span>
							</div>
							<div class="flex flex-row justify-between gap-3 border-t-2 border-line pt-3 text-sm font-bold text-ink">
								<span>{{ __("Total earnings") }}</span><span>{{ money(slip.gross_pay) }}</span>
							</div>

							<h2 class="pb-2 pt-6 text-base font-bold text-ink lg:text-lg">{{ __("Deductions") }}</h2>
							<div v-for="row in slip.deductions" :key="row.name" class="flex flex-row justify-between gap-3 border-t border-[#EEF0EE] py-2.5 text-sm">
								<span class="text-ink">{{ row.salary_component }}</span>
								<span class="font-semibold text-[#A8231A]">− {{ money(row.amount) }}</span>
							</div>
							<div v-if="!slip.deductions?.length" class="border-t border-[#EEF0EE] py-2.5 text-sm text-gray-700">{{ __("No deductions") }}</div>
							<div class="flex flex-row justify-between gap-3 border-t-2 border-line pt-3 text-sm font-bold text-ink">
								<span>{{ __("Take-home pay") }}</span><span>{{ money(slip.rounded_total || slip.net_pay) }}</span>
							</div>
						</section>

						<aside class="flex w-full flex-col gap-5 lg:w-[340px] lg:flex-none lg:gap-6">
							<section class="flex flex-col gap-2.5 rounded-2xl border border-line bg-white p-4 lg:p-6">
								<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("Attendance in this period") }}</h2>
								<div v-for="row in attendanceRows" :key="row.label" class="flex flex-row justify-between gap-3 text-sm">
									<span class="text-gray-700">{{ row.label }}</span>
									<span class="font-semibold text-ink">{{ row.value }}</span>
								</div>
							</section>
							<section class="flex flex-col gap-2.5 rounded-2xl border border-line bg-white p-4 lg:p-6">
								<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("Details") }}</h2>
								<div class="flex flex-row justify-between gap-3 text-sm">
									<span class="text-gray-700">{{ __("Period") }}</span>
									<span class="text-right font-semibold text-ink">
										{{ dayjs(slip.start_date).format("D MMM YYYY") }} – {{ dayjs(slip.end_date).format("D MMM YYYY") }}
									</span>
								</div>
								<div v-if="slip.posting_date" class="flex flex-row justify-between gap-3 text-sm">
									<span class="text-gray-700">{{ __("Slip date") }}</span>
									<span class="font-semibold text-ink">{{ dayjs(slip.posting_date).format("D MMM YYYY") }}</span>
								</div>
								<div v-if="slip.bank_name" class="flex flex-row justify-between gap-3 text-sm">
									<span class="text-gray-700">{{ __("Bank") }}</span>
									<span class="font-semibold text-ink">{{ slip.bank_name }}</span>
								</div>
							</section>
						</aside>
					</div>
				</template>
				<div v-else-if="resource.loading" class="py-10 text-center text-sm text-gray-700">{{ __("Loading…") }}</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { createResource } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { formatCurrency } from "@/utils/formatters"
import { downloadSlipPDF, slipPeriod } from "@/utils/salarySlip"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const props = defineProps({
	id: {
		type: String,
		required: true,
	},
})

// employees can read only their own slips (Salary Slip has_permission)
const resource = createResource({ url: "frappe.client.get" })
watch(
	() => props.id,
	(name) => name && resource.submit({ doctype: "Salary Slip", name }),
	{ immediate: true }
)
const slip = computed(() => resource.data)
const money = (value) => formatCurrency(value || 0, slip.value?.currency)

const attendanceRows = computed(() => {
	const s = slip.value
	if (!s) return []
	return [
		{ label: __("Working days"), value: s.total_working_days },
		{ label: __("Paid days"), value: s.payment_days },
		s.absent_days && { label: __("Absent days"), value: s.absent_days },
		s.leave_without_pay && { label: __("Unpaid leave days"), value: s.leave_without_pay },
		s.late_entry_days && { label: __("Late days"), value: s.late_entry_days },
	].filter(Boolean)
})

const downloading = ref(false)
const downloadError = ref("")
async function download() {
	downloading.value = true
	downloadError.value = ""
	try {
		await downloadSlipPDF(slip.value.name)
	} catch (error) {
		downloadError.value = __("The PDF could not be downloaded: {0}", [error.message])
	} finally {
		downloading.value = false
	}
}
</script>

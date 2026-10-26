<template>
	<BaseLayout :pageTitle="__('Salary')">
		<template #body>
			<div class="flex w-full flex-col gap-5 px-4 pb-24 pt-5 lg:gap-6 lg:px-6">
				<section class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 lg:p-6">
					<div class="flex flex-row flex-wrap items-center justify-between gap-3">
						<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("All salary slips") }}</h2>
						<!-- amounts stay hidden until asked for, so a glance at the phone shows no salary -->
						<button
							v-if="slips.data?.length"
							type="button"
							:aria-pressed="showAmounts"
							class="flex min-h-[36px] items-center gap-1.5 rounded-lg px-2 text-sm font-semibold text-brand-600 hover:text-brand-700 lg:ml-auto"
							@click="showAmounts = !showAmounts"
						>
							<FeatherIcon :name="showAmounts ? 'eye-off' : 'eye'" class="h-4 w-4" />
							{{ showAmounts ? __("Hide amounts") : __("Show amounts") }}
						</button>
						<div
							v-if="years.length > 1"
							role="tablist"
							:aria-label="__('Year')"
							class="flex flex-row gap-1 rounded-xl bg-[#F1F3F0] p-1"
						>
							<button
								v-for="year in years"
								:key="year"
								type="button"
								role="tab"
								:aria-selected="activeYear === year"
								:class="[
									'min-h-[36px] rounded-lg px-3.5 text-sm',
									activeYear === year ? 'bg-white font-semibold text-ink shadow-sm' : 'font-medium text-gray-700',
								]"
								@click="activeYear = year"
							>
								{{ year }}
							</button>
						</div>
					</div>

					<router-link
						v-for="slip in shown"
						:key="slip.name"
						:to="{ name: 'SalarySlipDetailView', params: { id: slip.name } }"
						class="flex flex-row items-center gap-4 rounded-xl border border-line p-3.5 hover:border-gray-400 lg:p-4"
					>
						<span class="flex h-11 w-11 flex-none flex-col items-center justify-center rounded-xl bg-page">
							<span class="text-[11px] font-semibold uppercase text-gray-700">{{ dayjs(slip.end_date).format("MMM") }}</span>
							<span class="text-[13px] font-bold leading-none text-ink">{{ dayjs(slip.end_date).format("YYYY") }}</span>
						</span>
						<span class="flex min-w-0 flex-1 flex-col gap-0.5">
							<span class="text-sm font-semibold text-ink lg:text-[15px]">{{ slipPeriod(slip) }}</span>
							<span v-if="showAmounts" class="hidden text-[13px] text-gray-700 lg:block">
								{{ __("Gross {0}", [formatCurrency(slip.gross_pay, slip.currency)]) }}
							</span>
						</span>
						<span class="text-right text-[15px] font-semibold tabular-nums text-ink">
							{{ showAmounts ? formatCurrency(slip.net_pay, slip.currency) : "••••••" }}
						</span>
						<FeatherIcon name="chevron-right" class="h-5 w-5 flex-none text-gray-500" />
					</router-link>

					<div
						v-if="slips.fetched && !slips.data?.length"
						class="rounded-xl border border-dashed border-[#D5DAD4] p-6 text-center text-sm leading-relaxed text-gray-700"
					>
						{{ __("No salary slips yet. Your slip appears here once payroll for the period is approved.") }}
					</div>
				</section>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"
import { createListResource, FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { formatCurrency } from "@/utils/formatters"
import { slipPeriod } from "@/utils/salarySlip"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

// every submitted slip of the employee, newest first; no Payroll Period needed
const slips = createListResource({
	doctype: "Salary Slip",
	fields: ["name", "start_date", "end_date", "posting_date", "currency", "gross_pay", "total_deduction", "net_pay"],
	filters: { employee: employee.data?.name, docstatus: 1 },
	orderBy: "end_date desc",
	pageLength: 100,
	auto: true,
})
onIonViewWillEnter(() => slips.reload())

const years = computed(() => [...new Set((slips.data || []).map((slip) => dayjs(slip.end_date).format("YYYY")))])
const activeYear = ref("")
watch(years, (list) => {
	if (!list.includes(activeYear.value)) activeYear.value = list[0] || ""
})
const shown = computed(() =>
	(slips.data || []).filter((slip) => !activeYear.value || dayjs(slip.end_date).format("YYYY") === activeYear.value)
)

// hidden again each time the page opens
const showAmounts = ref(false)
onIonViewWillEnter(() => (showAmounts.value = false))
</script>

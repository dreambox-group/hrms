<template>
	<section
		v-if="showReimbursements"
		:aria-label="__('Reimbursement')"
		class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 lg:p-6"
	>
		<div class="flex flex-row items-start justify-between gap-3">
			<div>
				<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("Reimbursement") }}</h2>
				<p class="text-[13px] text-gray-700">{{ __("Paid for something for work? Claim it back.") }}</p>
			</div>
			<router-link :to="{ name: 'Reimbursements' }" class="whitespace-nowrap text-sm font-semibold text-brand-600">
				{{ __("See all") }}
			</router-link>
		</div>

		<router-link
			v-for="row in latestReimbursements.data?.items || []"
			:key="row.id"
			:to="{ name: 'ReimbursementDetail', params: { id: row.id } }"
			class="flex flex-row items-center gap-3 border-t border-[#EEF0EE] pt-3"
		>
			<span class="flex min-w-0 flex-1 flex-col">
				<span class="truncate text-sm font-semibold text-ink">{{ row.description }}</span>
				<span class="text-[13px] text-gray-700">{{ formatCurrency(row.amount, "IDR") }}</span>
			</span>
			<span :class="['whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[PROGRESS_TONE[row.progress.state]]]">
				{{ __(row.progress.word) }}
			</span>
		</router-link>

		<router-link
			:to="{ name: 'ReimbursementNew' }"
			class="flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-line px-4 text-[15px] font-semibold text-ink hover:bg-gray-50"
		>
			<FeatherIcon name="plus" class="h-4 w-4" />
			{{ __("New reimbursement") }}
		</router-link>
	</section>
</template>

<script setup>
import { inject, watch } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"
import { FeatherIcon } from "frappe-ui"

import { latestReimbursements, PROGRESS_TONE } from "@/data/reimbursements"
import { formatCurrency } from "@/utils/formatters"
import { showReimbursements } from "@/utils/navigation"
import { TONE_CLASSES } from "@/utils/status"

const __ = inject("$translate")

// loaded only once the settings say Drea Finance is connected
watch(showReimbursements, (on) => on && latestReimbursements.reload(), { immediate: true })
onIonViewWillEnter(() => showReimbursements.value && latestReimbursements.reload())
</script>

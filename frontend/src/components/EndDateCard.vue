<template>
	<!-- Employee Types without Leave Allocation: their leave moves the contract end date -->
	<div class="flex flex-col gap-2">
		<template v-if="details.contract_end_date">
			<span class="text-sm text-gray-700">{{ __("Contract ends on") }}</span>
			<span class="text-[26px] font-bold leading-tight tracking-tight text-ink">
				{{ dayjs(details.contract_end_date).format("ddd D MMM YYYY") }}
			</span>
			<span
				v-if="details.days_moved"
				class="rounded-xl bg-[#E4ECFB] px-3 py-2 text-[13px] leading-snug text-[#1E55B8]"
			>
				{{
					details.days_moved == 1
						? __("Originally {0}. Moved 1 working day for your leave.", [originalLabel])
						: __("Originally {0}. Moved {1} working days for your leave.", [originalLabel, details.days_moved])
				}}
			</span>
		</template>
		<span v-else class="text-sm text-gray-700">{{ __("No contract end date is set yet. Ask HR.") }}</span>
		<span class="text-[13px] leading-snug text-gray-700">
			{{ __("No leave allocation: each leave day moves your end date by one working day.") }}
		</span>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const props = defineProps({ details: { type: Object, required: true } })

const originalLabel = computed(() => dayjs(props.details.original_contract_end_date).format("ddd D MMM"))
</script>

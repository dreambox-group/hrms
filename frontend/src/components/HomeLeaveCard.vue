<template>
	<section :aria-label="__('Leave')" class="flex flex-col gap-4 rounded-2xl border border-line bg-white p-4 lg:p-6">
		<h3 class="text-base font-bold text-ink lg:text-lg">{{ __("Leave") }}</h3>
		<EndDateCard v-if="endDate" :details="endDate" />
		<template v-else>
		<div v-for="(row, index) in balances" :key="row.type">
			<div class="flex flex-row items-baseline gap-2">
				<span :class="['font-bold leading-none tracking-tight text-ink', index ? 'text-2xl' : 'text-[40px]']">
					{{ row.left }}
				</span>
				<span class="text-[15px] text-gray-700">{{ __("of {0} {1} days left", [row.total, row.type]) }}</span>
			</div>
			<LeaveBar :row="row" class="mt-3" />
		</div>
		<div v-if="leaveBalance.fetched && !balances.length" class="text-sm text-gray-700">
			{{ __("You have no paid leave allocated.") }}
		</div>
		</template>
		<button
			type="button"
			class="flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-brand-600 text-[15px] font-semibold text-brand-600 hover:bg-brand-50"
			@click="openLeaveRequest(router, isDesktop)"
		>
			<FeatherIcon name="plus" class="h-4 w-4" />
			{{ __("Request leave") }}
		</button>
	</section>
</template>

<script setup>
import { computed, inject } from "vue"
import { useRouter } from "vue-router"
import { FeatherIcon } from "frappe-ui"

import EndDateCard from "@/components/EndDateCard.vue"
import LeaveBar from "@/components/LeaveBar.vue"
import { useIsDesktop } from "@/composables/useIsDesktop"
import { openLeaveRequest } from "@/composables/leaveRequest"
import { homeData } from "@/data/home"
import { leaveBalance, balanceRows } from "@/data/leaves"

const __ = inject("$translate")
const router = useRouter()
const isDesktop = useIsDesktop()

const balances = computed(() => balanceRows(leaveBalance.data))
// Employee Types without Leave Allocation see their contract end date instead of a balance
const endDate = computed(() => homeData.data?.end_date || null)
</script>

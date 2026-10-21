<template>
	<div v-if="rows.length" class="flex flex-col border-t pt-2">
		<router-link
			v-for="row in rows"
			:key="row.doctype"
			:to="{ name: row.route }"
			class="flex flex-row justify-between items-center py-2 text-sm text-gray-800"
		>
			<span>{{ __("{0} waiting for you", [row.label]) }}</span>
			<span class="rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white">{{ row.count }}</span>
		</router-link>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"

import { homeData } from "@/data/home"
import { showExpenses } from "@/utils/navigation"

const __ = inject("$translate")

// these are approved from their own dashboards' Team Requests
const ROUTES = {
	"Expense Claim": "ExpenseClaimsDashboard",
	"Shift Request": "AttendanceDashboard",
}

const rows = computed(() =>
	(homeData.data?.other_approvals || [])
		.filter((row) => row.count && (showExpenses.value || row.doctype !== "Expense Claim"))
		.map((row) => ({ ...row, route: ROUTES[row.doctype] }))
)
</script>

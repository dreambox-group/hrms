<template>
	<section
		v-if="summary.data?.enabled"
		:aria-label="__('Cuti Pengganti')"
		class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 lg:p-6"
	>
		<div class="flex flex-row items-start justify-between gap-3">
			<div>
				<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("Cuti Pengganti") }}</h2>
				<p class="text-[13px] text-gray-700">{{ __("Days off for overtime") }}</p>
			</div>
			<div class="text-right">
				<div class="text-[32px] font-bold leading-none tracking-tight text-ink">{{ summary.data.available }}</div>
				<div class="text-[13px] text-gray-700">{{ summary.data.available == 1 ? __("day to use") : __("days to use") }}</div>
			</div>
		</div>

		<div
			v-if="summary.data.next_expiry"
			class="rounded-xl bg-[#FDEFD6] px-3.5 py-2.5 text-[13px] leading-snug text-[#8A4B00]"
		>
			{{
				__("{0} expires on {1}. Use it with Request leave → {2}.", [
					summary.data.next_expiry.days == 1 ? __("1 day") : __("{0} days", [summary.data.next_expiry.days]),
					dayjs(summary.data.next_expiry.date).format("ddd D MMM YYYY"),
					summary.data.leave_type,
				])
			}}
		</div>

		<button
			type="button"
			class="flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-line px-4 text-[15px] font-semibold text-ink hover:bg-gray-50"
			@click="formOpen = true"
		>
			<FeatherIcon name="plus" class="h-4 w-4" />
			{{ __("I worked overtime") }}
		</button>

		<div
			v-for="row in shown"
			:key="row.name"
			class="flex flex-row items-center gap-3 border-t border-[#EEF0EE] pt-3"
		>
			<span class="flex h-11 w-11 flex-none flex-col items-center justify-center rounded-xl bg-page">
				<span class="text-[11px] font-semibold uppercase text-gray-700">{{ dayjs(row.work_from_date).format("MMM") }}</span>
				<span class="text-base font-bold leading-none text-ink">{{ dayjs(row.work_from_date).format("D") }}</span>
			</span>
			<span class="flex min-w-0 flex-1 flex-col gap-0.5">
				<span class="truncate text-sm font-semibold text-ink">{{ row.reason }}</span>
				<span class="text-[13px] text-gray-700">{{ rowNote(row) }}</span>
			</span>
			<span class="flex flex-col items-end gap-1">
				<span :class="['whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[rowTone(row)]]">
					{{ rowLabel(row) }}
				</span>
				<button
					v-if="row.status === 'Open' && row.docstatus === 0"
					type="button"
					class="text-xs font-semibold text-gray-700 hover:text-[#A8231A]"
					:disabled="withdraw.loading"
					@click="withdrawRequest(row.name)"
				>
					{{ __("Withdraw") }}
				</button>
			</span>
		</div>
		<button
			v-if="(summary.data.requests || []).length > 4"
			type="button"
			class="self-start pt-1 text-sm font-semibold text-brand-600"
			@click="showAll = !showAll"
		>
			{{ showAll ? __("Show less") : __("Show all") }}
		</button>
	</section>

	<ion-modal
		:is-open="formOpen"
		:class="isDesktop ? 'centered-dialog' : ''"
		:initial-breakpoint="isDesktop ? undefined : 1"
		:breakpoints="isDesktop ? undefined : [0, 1]"
		@didDismiss="formOpen = false"
	>
		<div class="flex max-h-[90vh] w-full flex-col overflow-y-auto bg-white">
			<div class="flex flex-row items-center justify-between border-b border-[#EEF0EE] px-5 py-4">
				<h1 class="text-xl font-bold text-ink">{{ __("Cuti Pengganti") }}</h1>
				<button
					type="button"
					class="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-ink"
					:aria-label="__('Close')"
					@click="formOpen = false"
				>
					<FeatherIcon name="x" class="h-5 w-5" />
				</button>
			</div>
			<CutiPenggantiForm
				v-if="formOpen"
				:months="summary.data?.months || 3"
				@sent="summary.reload()"
				@close="formOpen = false"
			/>
		</div>
	</ion-modal>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { IonModal, onIonViewWillEnter } from "@ionic/vue"
import { createResource, FeatherIcon, toast } from "frappe-ui"

import CutiPenggantiForm from "@/components/CutiPenggantiForm.vue"
import { useIsDesktop } from "@/composables/useIsDesktop"
import { TONE_CLASSES } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const isDesktop = useIsDesktop()

const summary = createResource({ url: "hrms.api.employee_app.get_my_cuti_pengganti", auto: true })
onIonViewWillEnter(() => summary.reload())

const formOpen = ref(false)
const showAll = ref(false)
const shown = computed(() => (showAll.value ? summary.data?.requests || [] : (summary.data?.requests || []).slice(0, 4)))

function rowLabel(row) {
	if (row.status === "Open") return __("Waiting")
	if (row.status === "Rejected") return __("Rejected")
	if (row.expired) return __("Expired")
	return row.left ? __("{0} left", [row.left]) : __("Used")
}
function rowTone(row) {
	if (row.status === "Open") return "warn"
	if (row.status === "Rejected") return "bad"
	if (row.expired || !row.left) return "neutral"
	return "ok"
}
function rowNote(row) {
	const days = row.days == 1 ? __("1 day") : __("{0} days", [row.days])
	if (row.status !== "Approved" || !row.expires_on) return days
	const date = dayjs(row.expires_on).format("D MMM YYYY")
	return row.expired ? __("{0} · expired {1}", [days, date]) : __("{0} · usable until {1}", [days, date])
}

const withdraw = createResource({ url: "hrms.api.employee_app.withdraw_cuti_pengganti" })
function withdrawRequest(name) {
	withdraw.submit(
		{ name },
		{
			onSuccess: () => summary.reload(),
			onError(error) {
				toast({
					title: __("Error"),
					text: error.messages?.[0] || __("The request could not be withdrawn."),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			},
		}
	)
}
</script>

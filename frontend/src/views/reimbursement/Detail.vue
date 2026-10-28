<template>
	<BaseLayout :pageTitle="claim.data?.code || __('Reimbursement')">
		<template #body>
			<div class="flex w-full max-w-[720px] flex-col gap-4 px-4 pb-24 pt-5 lg:gap-5 lg:px-6">
				<router-link :to="{ name: 'Reimbursements' }" class="flex items-center gap-1 self-start text-sm font-semibold text-brand-600">
					<FeatherIcon name="chevron-left" class="h-4 w-4" />
					{{ __("All reimbursements") }}
				</router-link>

				<div v-if="claim.error" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
					{{ claim.error.messages?.[0] || __("This reimbursement could not be loaded.") }}
				</div>

				<template v-if="claim.data">
					<!-- where it is now -->
					<section class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 lg:p-5">
						<div class="flex flex-row items-start justify-between gap-3">
							<div class="min-w-0">
								<h2 class="text-lg font-bold text-ink">{{ claim.data.description }}</h2>
								<p class="text-[13px] text-gray-700">{{ claim.data.code }}</p>
							</div>
							<div class="text-right">
								<div class="text-xl font-bold text-ink">{{ formatCurrency(claim.data.amount, "IDR") }}</div>
								<span :class="['mt-1 inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[PROGRESS_TONE[claim.data.progress.state]]]">
									{{ __(claim.data.progress.word) }}
								</span>
							</div>
						</div>

						<!-- progress -->
						<ol class="mt-1 flex flex-col">
							<li v-for="(step, i) in claim.data.steps" :key="i" class="flex flex-row gap-3">
								<span class="flex flex-col items-center">
									<span :class="['mt-1 h-3 w-3 rounded-full', stepTone(step)]"></span>
									<span v-if="i < claim.data.steps.length - 1 || waiting" class="w-px flex-1 bg-line"></span>
								</span>
								<span class="flex flex-col pb-4">
									<span class="text-sm font-semibold text-ink">{{ __(step.what) }}</span>
									<span class="text-[13px] text-gray-700">
										{{ dayjs(step.at).format("ddd D MMM YYYY, HH:mm") }}{{ step.by ? ` · ${step.by}` : "" }}
									</span>
									<span v-if="step.note" class="mt-1 rounded-lg bg-page px-2.5 py-1.5 text-[13px] text-ink">{{ step.note }}</span>
								</span>
							</li>
							<li v-if="waiting" class="flex flex-row gap-3">
								<span class="mt-1 h-3 w-3 rounded-full border-2 border-[#8A4B00] bg-white"></span>
								<span class="text-sm font-semibold text-[#8A4B00]">{{ __(claim.data.progress.word) }}</span>
							</li>
						</ol>
					</section>

					<!-- what was sent -->
					<section class="flex flex-col gap-2 rounded-2xl border border-line bg-white p-4 lg:p-5">
						<h2 class="pb-1 text-base font-bold text-ink">{{ __("Details") }}</h2>
						<Row :label="__('Category')" :value="claim.data.category" />
						<Row :label="__('Date of the expense')" :value="dayjs(claim.data.expense_date).format('D MMMM YYYY')" />
						<Row :label="__('Billed to the client?')" :value="claim.data.billed_to_client" />
						<Row v-if="claim.data.notes" :label="__('More notes')" :value="claim.data.notes" />
						<Row :label="__('Account holder name')" :value="claim.data.payee.account_name" />
						<Row :label="__('Bank / e-wallet')" :value="claim.data.payee.provider" />
						<Row :label="__('Account number')" :value="claim.data.payee.account_number" />
						<Row :label="__('Proof')" :value="claim.data.files.map((f) => `${f.name} (${f.type})`).join(', ')" />
					</section>

					<div v-if="cancelError" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{{ cancelError }}</div>
					<div v-if="claim.data.can_cancel" class="flex flex-col gap-2">
						<template v-if="confirming">
							<textarea
								v-model="reason"
								rows="2"
								:placeholder="__('Why? (optional)')"
								class="rounded-xl border border-[#D5DAD4] px-3.5 py-2.5 text-[15px] text-ink focus:border-brand-600 focus:ring-brand-600"
							></textarea>
							<div class="flex flex-row gap-2">
								<button type="button" class="flex-1 rounded-xl bg-[#A8231A] py-3 text-sm font-semibold text-white disabled:opacity-50" :disabled="cancelling" @click="cancel">
									{{ cancelling ? __("Cancelling…") : __("Yes, cancel it") }}
								</button>
								<button type="button" class="flex-1 rounded-xl border border-line py-3 text-sm font-semibold text-ink" @click="confirming = false">
									{{ __("Keep it") }}
								</button>
							</div>
						</template>
						<button v-else type="button" class="self-start rounded-xl border border-line px-5 py-2.5 text-sm font-semibold text-ink hover:bg-gray-50" @click="confirming = true">
							{{ __("Cancel") }}
						</button>
					</div>
				</template>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, defineComponent, h, inject, ref } from "vue"
import { useRoute } from "vue-router"
import { onIonViewWillEnter } from "@ionic/vue"
import { call, createResource, FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { latestReimbursements, PROGRESS_TONE } from "@/data/reimbursements"
import { formatCurrency } from "@/utils/formatters"
import { TONE_CLASSES } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const route = useRoute()

const Row = defineComponent({
	props: { label: String, value: String },
	setup(props) {
		return () =>
			h("div", { class: "flex flex-row justify-between gap-4 border-t border-[#EEF0EE] pt-2 text-sm" }, [
				h("span", { class: "text-gray-700" }, props.label),
				h("span", { class: "text-right font-medium text-ink" }, props.value || "–"),
			])
	},
})

const claim = createResource({
	url: "hrms.api.reimbursements.get_reimbursement",
	makeParams: () => ({ name: route.params.id }),
	auto: true,
})
onIonViewWillEnter(() => claim.reload())

const waiting = computed(() => ["waiting", "approved"].includes(claim.data?.progress?.state))
function stepTone(step) {
	if (/Rejected|withdrawn/.test(step.what)) return "bg-[#A8231A]"
	if (step.what === "Paid") return "bg-[#0F6B4C]"
	return "bg-brand-600"
}

const confirming = ref(false)
const reason = ref("")
const cancelling = ref(false)
const cancelError = ref("")
async function cancel() {
	cancelling.value = true
	cancelError.value = ""
	try {
		await call("hrms.api.reimbursements.cancel_reimbursement", { name: route.params.id, reason: reason.value })
		confirming.value = false
		claim.reload()
		latestReimbursements.reload()
	} catch (err) {
		cancelError.value = err.messages?.[0] || __("It could not be cancelled.")
	} finally {
		cancelling.value = false
	}
}
</script>

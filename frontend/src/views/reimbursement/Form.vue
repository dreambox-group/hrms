<template>
	<BaseLayout :pageTitle="__('New reimbursement')">
		<template #body>
			<div class="flex w-full max-w-[720px] flex-col gap-5 px-4 pb-24 pt-5 lg:px-6">
				<div v-if="options.error" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
					{{ options.error.messages?.[0] || __("Drea Finance can't be reached right now. Try again in a moment.") }}
				</div>

				<template v-if="!sent">
					<!-- 1. proof -->
					<section class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 lg:p-5">
						<h2 class="text-base font-bold text-ink">{{ label("evidence") }} <span class="text-[#A8231A]">*</span></h2>
						<p class="text-[13px] text-gray-700">{{ __("Photos or PDFs, up to {0} MB each. Say what each file is.", [maxMb]) }}</p>
						<div v-for="(row, i) in files" :key="row.key" class="flex flex-col gap-2 rounded-xl border border-[#EEF0EE] p-3 sm:flex-row sm:items-center">
							<span class="flex min-w-0 flex-1 items-center gap-2">
								<FeatherIcon :name="row.file.type === 'application/pdf' ? 'file-text' : 'image'" class="h-4 w-4 flex-none text-gray-700" />
								<span class="truncate text-sm text-ink">{{ row.file.name }}</span>
							</span>
							<select
								v-model="row.category"
								:aria-label="label('file_category')"
								class="min-h-[40px] rounded-lg border border-[#D5DAD4] bg-white px-2.5 text-sm text-ink focus:border-brand-600 focus:ring-brand-600"
							>
								<option value="" disabled>{{ label("file_category") }}…</option>
								<option v-for="type in options.data?.file_categories || []" :key="type.value" :value="type.value">{{ type.label }}</option>
							</select>
							<button type="button" class="text-sm font-semibold text-gray-700 hover:text-[#A8231A]" @click="files.splice(i, 1)">
								{{ __("Remove") }}
							</button>
						</div>
						<label class="flex min-h-[48px] cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-[#B9C0B8] text-[15px] font-semibold text-ink hover:bg-gray-50">
							<FeatherIcon name="upload" class="h-4 w-4" />
							{{ __("Add files") }}
							<input type="file" multiple class="hidden" :accept="accept" @change="addFiles" />
						</label>
					</section>

					<!-- 2. the expense -->
					<section class="flex flex-col gap-4 rounded-2xl border border-line bg-white p-4 lg:p-5">
						<h2 class="text-base font-bold text-ink">{{ __("Expense") }}</h2>
						<Field :label="label('expense_category')" required>
							<select v-model="form.expense_category" :class="FIELD">
								<option value="" disabled>{{ __("Choose") }}…</option>
								<option v-for="c in options.data?.categories || []" :key="c.value" :value="c.value">{{ c.label }}</option>
							</select>
						</Field>
						<Field :label="label('description')" :hint="hint('description')" required>
							<input v-model="form.description" type="text" :class="FIELD" />
						</Field>
						<div class="grid gap-4 sm:grid-cols-2">
							<Field :label="label('amount')" required>
								<div class="flex items-center rounded-xl border border-[#D5DAD4] bg-white focus-within:border-brand-600">
									<span class="pl-3.5 text-[15px] text-gray-700">Rp</span>
									<input v-model="form.amount" type="text" inputmode="numeric" class="min-h-[44px] w-full border-0 bg-transparent px-2 text-[15px] text-ink focus:ring-0" @input="formatAmount" />
								</div>
							</Field>
							<Field :label="label('expense_date')" required>
								<input v-model="form.expense_date" type="date" :max="today" :class="FIELD" />
							</Field>
						</div>
						<Field :label="label('cost_responsibility')" :hint="hint('cost_responsibility')" required group>
							<div class="flex flex-col gap-2 sm:flex-row">
								<label
									v-for="option in options.data?.cost_responsibility || []"
									:key="option.value"
									:class="[
										'flex min-h-[44px] flex-1 cursor-pointer items-center gap-2 rounded-xl border px-3.5 text-sm',
										form.cost_responsibility === option.value ? 'border-brand-600 bg-brand-50 font-semibold text-ink' : 'border-[#D5DAD4] text-ink',
									]"
								>
									<input v-model="form.cost_responsibility" type="radio" :value="option.value" class="text-brand-600 focus:ring-brand-600" />
									{{ option.label }}
								</label>
							</div>
						</Field>
						<Field :label="label('notes')" :hint="hint('notes')">
							<textarea v-model="form.notes" rows="2" :class="[FIELD, 'py-2.5']"></textarea>
						</Field>
					</section>

					<!-- 3. who gets paid -->
					<section class="flex flex-col gap-4 rounded-2xl border border-line bg-white p-4 lg:p-5">
						<h2 class="text-base font-bold text-ink">{{ __("Who gets paid") }}</h2>
						<Field :label="label('payee_account_name')" :hint="hint('payee_account_name')" required>
							<input v-model="form.payee_account_name" type="text" :class="FIELD" />
						</Field>
						<div class="grid gap-4 sm:grid-cols-2">
							<Field :label="label('account_provider')" required>
								<input v-model="form.account_provider" type="text" list="reimburse-providers" :class="FIELD" autocomplete="off" />
								<datalist id="reimburse-providers">
									<option v-for="name in providers" :key="name" :value="name" />
								</datalist>
							</Field>
							<Field :label="label('account_number')" :hint="hint('account_number')" required>
								<input v-model="form.account_number" type="text" inputmode="numeric" :class="FIELD" />
							</Field>
						</div>
						<Field :label="label('payee_tax_id')" :hint="hint('payee_tax_id')" required>
							<input v-model="form.payee_tax_id" type="text" inputmode="numeric" :class="FIELD" />
						</Field>
					</section>

					<div v-if="error" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{{ error }}</div>

					<button
						type="button"
						class="flex min-h-[52px] w-full items-center justify-center rounded-xl bg-brand-600 text-base font-semibold text-white hover:bg-brand-700 disabled:bg-gray-300 disabled:text-gray-600"
						:disabled="sending || !options.data"
						@click="send"
					>
						{{ sending ? __("Sending…") : __("Submit") }}
					</button>
				</template>

				<div v-else class="flex flex-col items-center gap-3 rounded-2xl border border-line bg-white px-5 py-10 text-center">
					<span class="flex h-12 w-12 items-center justify-center rounded-full bg-[#E2F4EA] text-[#0F6B4C]">
						<FeatherIcon name="check" class="h-6 w-6" />
					</span>
					<h2 class="text-xl font-bold text-ink">{{ __("Sent to Drea Finance") }}</h2>
					<p class="max-w-[420px] text-sm text-gray-700">
						{{ __("{0}. Finance places it first, then it goes for approval. You can follow it here.", [sent.code]) }}
					</p>
					<div class="mt-2 flex flex-row gap-2">
						<router-link :to="{ name: 'ReimbursementDetail', params: { id: sent.id } }" class="rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white">
							{{ __("See its progress") }}
						</router-link>
						<router-link :to="{ name: 'Reimbursements' }" class="rounded-xl border border-line px-5 py-2.5 text-sm font-semibold text-ink">
							{{ __("All reimbursements") }}
						</router-link>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, defineComponent, h, inject, reactive, ref } from "vue"
import { call, createResource, FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { latestReimbursements, uploadProof } from "@/data/reimbursements"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

// a labelled field, with Drea Finance's hint under it; the label wraps the input so it names it,
// and a set of choices is a fieldset named by its legend
const Field = defineComponent({
	props: { label: String, hint: String, required: Boolean, group: Boolean },
	setup(props, { slots }) {
		return () => {
			const title = [props.label, props.required ? h("span", { class: "text-[#A8231A]" }, " *") : null]
			const hint = props.hint ? h("p", { class: "text-[13px] font-normal text-gray-700" }, props.hint) : null
			if (props.group) {
				return h("fieldset", { class: "flex flex-col gap-1.5" }, [
					h("legend", { class: "mb-1.5 text-sm font-semibold text-ink" }, title),
					slots.default?.(),
					hint,
				])
			}
			return h("label", { class: "flex flex-col gap-1.5" }, [
				h("span", { class: "text-sm font-semibold text-ink" }, title),
				slots.default?.(),
				hint,
			])
		}
	},
})

const FIELD =
	"min-h-[44px] w-full rounded-xl border border-[#D5DAD4] bg-white px-3.5 text-[15px] text-ink focus:border-brand-600 focus:ring-brand-600"
const today = dayjs().format("YYYY-MM-DD")
// the form's words and choices come from Drea Finance, so both forms read the same
const options = createResource({
	url: "hrms.api.reimbursements.get_reimbursement_options",
	auto: true,
	onSuccess(data) {
		for (const [key, value] of Object.entries(data.prefill || {})) {
			if (value && !form[key]) form[key] = value
		}
	},
})
const label = (key) => options.data?.labels?.[key] || key
const hint = (key) => options.data?.hints?.[key] || ""
const maxMb = computed(() => Math.round((options.data?.max_file_bytes || 10 * 1024 * 1024) / 1024 / 1024))
const accept = computed(() => (options.data?.file_types || ["image/jpeg", "image/png", "application/pdf"]).join(","))
const providers = computed(() => (options.data?.providers || []).flatMap((group) => group.values || []))

const form = reactive({
	expense_category: "",
	description: "",
	amount: "",
	expense_date: today,
	cost_responsibility: "",
	notes: "",
	payee_account_name: "",
	account_provider: "",
	account_number: "",
	payee_tax_id: "",
})
const files = ref([])
const sending = ref(false)
const error = ref("")
const sent = ref(null)
let fileKey = 0

function addFiles(event) {
	error.value = ""
	const limit = options.data?.max_file_bytes || 10 * 1024 * 1024
	for (const file of event.target.files || []) {
		if (file.size > limit) {
			error.value = __("{0} is larger than {1} MB.", [file.name, maxMb.value])
			continue
		}
		// the type is chosen for each file, never assumed (as in Drea Finance)
		files.value.push({ key: ++fileKey, file, category: "", fileUrl: null })
	}
	event.target.value = ""
}

// 150000 → 150.000 as it is typed
function formatAmount() {
	const digits = String(form.amount).replace(/\D/g, "")
	form.amount = digits ? Number(digits).toLocaleString("id-ID") : ""
}

async function send() {
	error.value = ""
	if (!files.value.length) {
		error.value = __("Add the proof of the expense (invoice/receipt).")
		return
	}
	if (files.value.some((row) => !row.category)) {
		error.value = __("Say what each file is.")
		return
	}
	sending.value = true
	try {
		// uploaded once; a retry after a refusal sends the same files again
		for (const row of files.value) {
			if (!row.fileUrl) row.fileUrl = await uploadProof(row.file)
		}
		const result = await call("hrms.api.reimbursements.submit_reimbursement", {
			fields: { ...form, amount: String(form.amount).replace(/\D/g, "") },
			files: files.value.map((row) => ({ file_url: row.fileUrl, category: row.category })),
		})
		sent.value = { id: result.id, code: result.code }
		latestReimbursements.reload()
	} catch (err) {
		error.value = err.messages?.[0] || err.message || __("It could not be sent.")
		// the copies here were removed only on success; anything else keeps them for the retry
	} finally {
		sending.value = false
	}
}
</script>

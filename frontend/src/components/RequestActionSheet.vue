<template>
	<div
		v-if="document?.doc"
		class="bg-white w-full flex flex-col items-center justify-center pb-5 max-h-[calc(100vh-5rem)]"
	>
		<!-- Header -->
		<div
			class="w-full flex flex-row gap-2 pt-8 pb-5 border-b justify-center items-center sticky top-0 z-[100]"
		>
			<span class="text-gray-900 font-bold text-lg text-center">
				{{ __(document?.doctype) }}
			</span>
			<FeatherIcon
				v-if="props.showOpenForm"
				name="external-link"
				class="h-4 w-4 text-gray-500 cursor-pointer"
				@click="openFormView"
			/>
		</div>

		<!-- Request Summary -->
		<div class="w-full p-4 overflow-auto">
			<div class="flex flex-col items-center justify-center gap-5">
				<div
					v-for="field in fieldsWithValues"
					:key="field.fieldname"
					:class="[
						['Small Text', 'Text', 'Long Text', 'Table', 'geolocation'].includes(
							field.fieldtype
						)
							? 'flex-col'
							: 'flex-row items-center justify-between',
						'flex w-full',
					]"
				>
					<div class="text-gray-600 text-base">{{ __(field.label, null, props.modelValue?.doctype) }}</div>
					<component
						v-if="field.fieldtype === 'Table'"
						:is="field.component"
						:doc="document?.doc"
					/>
					<FormattedField
						v-else
						:value="field.value"
						:fieldtype="field.fieldtype"
						:fieldname="field.fieldname"
					/>
				</div>

				<!-- Attachments -->
				<div
					class="flex flex-col gap-2 w-full"
					v-if="attachedFiles?.data?.length"
				>
					<div class="text-gray-600 text-base">{{ __('Attachments') }}</div>
					<ul class="w-full flex flex-col items-center gap-2">
						<li
							class="bg-gray-100 rounded p-2 w-full"
							v-for="(file, index) in attachedFiles.data"
							:key="index"
						>
							<div
								class="flex flex-row items-center justify-between text-gray-700 text-sm"
							>
								<span class="grow" @click="showFilePreview(file)">
									{{ file.file_name || file.name }}
								</span>
							</div>
						</li>
					</ul>
				</div>
			</div>
		</div>

		<!-- Approvers of a leave request when leave is approved by levels -->
		<div v-if="leaveByLevels && document.doc.approvers?.length" class="w-full px-4 pb-4 flex flex-col gap-2">
			<div class="text-gray-600 text-base">{{ __("Approvers") }}</div>
			<div
				v-for="row in document.doc.approvers"
				:key="row.name"
				class="flex flex-row justify-between items-center text-sm"
			>
				<span>
					{{ row.approver_name || row.approver }}
					<span class="text-gray-500">· {{ __(row.approval_level) }}</span>
				</span>
				<span
					:class="[
						'rounded-full px-2 py-0.5 text-xs font-semibold',
						row.decision === 'Approved'
							? 'bg-green-100 text-green-800'
							: row.decision === 'Rejected'
							? 'bg-red-100 text-red-800'
							: 'bg-gray-100 text-gray-700',
					]"
				>
					{{ __(row.decision) }}
				</span>
			</div>
		</div>

		<!-- Actions -->
		<div
			v-if="leaveByLevels && document.doc.docstatus === 0 && document.doc.status === 'Open'"
			class="flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4"
		>
			<template v-if="myPendingApproval">
				<Button
					@click="recordDecision('Rejected')"
					:loading="leaveDecision.loading"
					class="w-full py-5"
					variant="subtle"
					theme="red"
				>
					<template #prefix>
						<FeatherIcon name="x" class="w-4" />
					</template>
					{{ __("Reject") }}
				</Button>
				<Button
					@click="recordDecision('Approved')"
					:loading="leaveDecision.loading"
					class="w-full py-5"
					variant="solid"
					theme="green"
				>
					<template #prefix>
						<FeatherIcon name="check" class="w-4" />
					</template>
					{{ __("Approve") }}
				</Button>
			</template>
			<div v-else class="w-full text-center text-sm text-gray-500">
				{{ __("Waiting for the other approvers.") }}
			</div>
		</div>

		<WorkflowActionSheet
			v-else-if="workflow?.hasWorkflow"
			:doc="document.doc"
			:workflow="workflow"
			view="actionSheet"
		/>

		<div
			v-else-if="['Open', 'Draft'].includes(document?.doc?.[approvalField]) && hasPermission('approval')"
			class="flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4"
		>
			<Button
				@click="updateDocumentStatus({ status: 'Rejected' })"
				class="w-full py-5"
				variant="subtle"
				theme="red"
			>
				<template #prefix>
					<FeatherIcon name="x" class="w-4" />
				</template>
				{{ __("Reject") }}
			</Button>

			<Button
				@click="updateDocumentStatus({ status: 'Approved' })"
				class="w-full py-5"
				variant="solid"
				theme="green"
			>
				<template #prefix>
					<FeatherIcon name="check" class="w-4" />
				</template>
				{{ __("Approve") }}
			</Button>
		</div>

		<div
			v-else-if="
				document?.doc?.docstatus === 0 &&
				(document?.doc?.doctype === 'Attendance Request' ||
					['Approved', 'Rejected'].includes(document?.doc?.[approvalField])) &&
				hasPermission('submit')
			"
			class="flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4"
		>
			<Button
				@click="updateDocumentStatus({ docstatus: 1 })"
				class="w-full py-5"
				variant="solid"
			>
				{{ __("Submit") }}
			</Button>
		</div>

		<div
			v-else-if="document?.doc?.docstatus === 1 && hasPermission('cancel')"
			class="flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4"
		>
			<Button
				@click="updateDocumentStatus({ docstatus: 2 })"
				class="w-full py-5"
				variant="subtle"
				theme="red"
			>
				<template #prefix>
					<FeatherIcon name="x" class="w-4" />
				</template>
				{{ __("Cancel") }}
			</Button>
		</div>

		<!-- File Preview Modal -->
		<ion-modal
			ref="modal"
			:is-open="showPreviewModal"
			@didDismiss="showPreviewModal = false"
		>
			<FilePreviewModal :file="selectedFile" />
		</ion-modal>
	</div>
</template>

<script setup>
import { computed, inject, ref, defineAsyncComponent, onMounted } from "vue"
import { IonModal, modalController } from "@ionic/vue"
import { useRouter } from "vue-router"
import {
	toast,
	createDocumentResource,
	createResource,
	FeatherIcon,
} from "frappe-ui"

import FormattedField from "@/components/FormattedField.vue"
import FilePreviewModal from "@/components/FilePreviewModal.vue"
import WorkflowActionSheet from "@/components/WorkflowActionSheet.vue"

import { getCompanyCurrency } from "@/data/currencies"
import { settings } from "@/data/settings"
import { homeData, leaveDecision } from "@/data/home"
import { teamLeaves } from "@/data/leaves"
import { formatCurrency } from "@/utils/formatters"

import useWorkflow from "@/composables/workflow"

const __ = inject("$translate")

const props = defineProps({
	fields: {
		type: Array,
		required: true,
	},
	showOpenForm: {
		type: Boolean,
		default: true,
	},
	modelValue: {
		type: Object,
		required: true,
	},
})
const router = useRouter()

let showPreviewModal = ref(false)
let selectedFile = ref({})
let workflow = ref(null)

function showFilePreview(fileObj) {
	selectedFile.value = fileObj
	showPreviewModal.value = true
}

const document = createDocumentResource({
	doctype: props.modelValue.doctype,
	name: props.modelValue.name,
	auto: true,
	onSuccess(doc) {
		attachedFiles.reload()
	},
})

const attachedFiles = createResource({
	url: "hrms.api.get_attachments",
	params: {
		dt: props.modelValue.doctype,
		dn: props.modelValue.name,
	},
})

const docPermissions = createResource({
	url: "frappe.client.get_doc_permissions",
	params: { doctype: props.modelValue.doctype, docname: props.modelValue.name },
	auto: true,
})

const permittedWriteFields = createResource({
	url: "hrms.api.get_permitted_fields_for_write",
	params: { doctype: props.modelValue.doctype },
	auto: true,
})

const sessionEmployee = inject("$employee")
const sessionUser = inject("$user")

// with approval by levels a leave request is decided through record_leave_decision, one vote each
const leaveByLevels = computed(
	() => props.modelValue.doctype === "Leave Application" && Boolean(settings.data?.leave_approval_by_levels)
)

const myPendingApproval = computed(() => {
	const approvers = document?.doc?.approvers || []
	const mine = approvers.find(
		(row) => row.approver === sessionUser?.data?.name && row.decision === "Pending"
	)
	if (!mine) return null
	// Regular approvers decide as one group: the first decision counts for all of them
	const regularDecided = approvers.some(
		(row) => row.approval_level === "Regular" && row.decision !== "Pending"
	)
	return mine.approval_level === "Regular" && regularDecided ? null : mine
})

function recordDecision(decision) {
	leaveDecision.submit(
		{ leave_application: document.doc.name, decision },
		{
			onSuccess(status) {
				document.reload()
				homeData.reload()
				teamLeaves.reload()
				modalController.dismiss()
				toast({
					title: __("Success"),
					text:
						status === "Open"
							? __("Your decision was saved. The request is still waiting for other approvers.")
							: __("The leave request is now {0}.", [__(status)]),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			},
			onError(error) {
				toast({
					title: __("Error"),
					text: error.messages?.[0] || __("Your decision could not be saved."),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			},
		}
	)
}

function hasPermission(action) {
	if (action === "approval" && props.modelValue.doctype === "Leave Application"){
		// prevent self leave approval
		const isSelfLeave = document?.doc?.employee === sessionEmployee?.data?.name 
		if (isSelfLeave && settings.data?.prevent_self_leave_approval)
			return false
		return permittedWriteFields.data?.includes(approvalField.value)
	}
	return docPermissions.data?.permissions[action]
}

const currency = computed(() => {
	let docCurrency = document?.doc?.currency

	if (!docCurrency && document?.doc?.company) {
		docCurrency = getCompanyCurrency(document?.doc?.company)
	}
	return docCurrency
})

const fieldsWithValues = computed(() => {
	return props.fields.filter((field) => {
		if (field.fieldtype === "Currency") {
			field.value = formatCurrency(
				document.doc?.[field.fieldname],
				currency.value
			)
		} else {
			if (field.fieldtype === "Table") {
				// dynamically loading child table component as per config
				// does not work with @ alias due to vite's import analysis
				field.component = defineAsyncComponent(() =>
					import(`../components/${field.componentName}.vue`)
				)
			}
			field.value =
				document?.doc?.[field.fieldname] || props.modelValue[field.fieldname]
		}

		return field.value
	})
})

const approvalField = computed(() => {
	return props.modelValue.doctype === "Expense Claim"
		? "approval_status"
		: "status"
})

const getSuccessMessage = ({ status = "", docstatus = 0 }) => {
	if (status) {
		return __("{0} successfully!", [__(status)])
	} else if (docstatus) {
		return __("Document {0} successfully!", [
			docstatus === 1 ? __("submitted") : __("cancelled")]
		)
	}
}

const getFailureMessage = ({ status = "", docstatus = 0 }) => {
	if (status) {
		return __("{0} failed!", [status === __("Approved") ? __("Approval") : __("Rejection")])
	} else if (docstatus) {
		return __('Document {0} failed!', [docstatus === 1 ? __("submission") : __("cancellation")])
	}
}

const updateDocumentStatus = ({ status = "", docstatus = 0 }) => {
	let updateValues = {}

	if (status) updateValues[approvalField.value] = status
	if (docstatus) updateValues.docstatus = docstatus

	document.setValue.submit(
		{ ...updateValues },
		{
			onSuccess() {
				if (docstatus !== 0) modalController.dismiss()

				toast({
					title: __("Success"),
					text: getSuccessMessage({ status, docstatus }),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			},
			onError() {
				toast({
					title: __("Error"),
					text: getFailureMessage({ status, docstatus }),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			},
		}
	)
}

const openFormView = () => {
	modalController.dismiss()
	router.push({
		name: `${props.modelValue.doctype.replace(/\s+/g, "")}DetailView`,
		params: { id: props.modelValue.name },
	})
}

onMounted(() => {
	workflow.value = useWorkflow(props.modelValue.doctype)
})

</script>

<style scoped>
ion-modal {
	--height: 100%;
}
</style>

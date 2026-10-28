<template>
	<ion-header class="ion-no-border">
		<div class="w-full sm:max-w-3xl sm:mx-auto">
			<div
				class="flex flex-row bg-white shadow-sm py-4 px-3 items-center justify-between border-b"
			>
				<div class="flex flex-row items-center">
					<Button variant="ghost" class="!px-1 mr-1 hover:bg-white" @click="router.back()">
						<FeatherIcon name="chevron-left" class="h-5 w-5" />
					</Button>
					<h2 class="text-xl font-semibold text-gray-900">{{ pageTitle }}</h2>
				</div>

				<div class="flex flex-row gap-2">
					<Button
						id="show-filter-modal"
						icon="filter"
						variant="subtle"
						@click="resetDraftFilters"
						:class="[
							areFiltersApplied
								? '!border !border-gray-800 !bg-white !text-gray-900 !font-semibold'
								: '',
						]"
					/>
					<router-link
						v-if="createPermission?.data?.has_permission && props.doctype != 'Employee Checkin'"
						:to="{ name: formViewRoute }"
						v-slot="{ navigate }"
					>
						<Button variant="solid" class="mr-2" @click="navigate">
							<template #prefix>
								<FeatherIcon name="plus" class="w-4" />
							</template>
							{{ __("New", null, props.doctype) }}
						</Button>
					</router-link>
				</div>
			</div>
		</div>
	</ion-header>

	<ion-content>
		<ion-refresher slot="fixed" @ionRefresh="handleRefresh($event)">
			<ion-refresher-content></ion-refresher-content>
		</ion-refresher>

		<div
			class="flex flex-col items-center mb-7 p-4 h-full w-full sm:max-w-3xl sm:mx-auto overflow-y-auto"
			ref="scrollContainer"
			@scroll="() => handleScroll()"
		>
			<div class="w-full">
				<TabButtons
					v-if="props.tabButtons"
					class="mt-5"
					:buttons="props.tabButtons"
					v-model="activeTab"
				/>

				<!-- kept on screen while the next page loads, so the scroll position stays -->
				<div class="flex flex-col bg-white rounded mt-5" v-if="rows.length">
					<div
						class="p-3.5 items-center justify-between border-b cursor-pointer"
						v-for="link in rows"
						:key="link.name"
					>
						<component
							v-if="props.doctype === 'Employee Checkin'"
							:is="listItemComponent[doctype]"
							:doc="link"
							:isTeamRequest="isTeamRequest"
							:workflowStateField="workflowStateField"
							@click="openRequestModal(link)"
						/>
						<router-link
							v-else
							:to="{ name: detailViewRoute, params: { id: link.name } }"
							v-slot="{ navigate }"
						>
							<component
								:is="listItemComponent[doctype]"
								:doc="link"
								:isTeamRequest="isTeamRequest"
								:workflowStateField="workflowStateField"
								@click="navigate"
							/>
						</router-link>
					</div>
				</div>
				<EmptyState
					:message="__('No {0} found', [props.doctype?.toLowerCase()])"
					v-else-if="!loading && fetched"
				/>

				<!-- Loading Indicator -->
				<div v-if="loading" class="flex mt-2 items-center justify-center">
					<LoadingIndicator class="w-8 h-8 text-gray-800" />
				</div>
			</div>
		</div>

		<CustomIonModal trigger="show-filter-modal">
			<!-- Filter Action Sheet -->
			<template #actionSheet>
				<ListFiltersActionSheet
					:filterConfig="filterConfig"
					@applyFilters="applyFilters"
					@clearFilters="clearFilters"
					v-model:filters="draftFilters"
				/>
			</template>
		</CustomIonModal>
	</ion-content>

	<ion-modal
		ref="modal"
		:is-open="isRequestModalOpen"
		@didDismiss="closeRequestModal"
		:initial-breakpoint="1"
		:breakpoints="[0, 1]"
	>
		<RequestActionSheet
			:fields="EMPLOYEE_CHECKIN_FIELDS"
			:showOpenForm="false"
			v-model="selectedRequest"
		/>
	</ion-modal>
</template>

<script setup>
import { useRouter } from "vue-router"
import { inject, ref, markRaw, watch, computed, reactive, onMounted, onBeforeUnmount } from "vue"
import {
	modalController,
	IonHeader,
	IonContent,
	IonModal,
	IonRefresher,
	IonRefresherContent,
} from "@ionic/vue"

import { FeatherIcon, call, createResource, LoadingIndicator, debounce } from "frappe-ui"

import TabButtons from "@/components/TabButtons.vue"
import EmployeeCheckinItem from "@/components/EmployeeCheckinItem.vue"
import AttendanceRequestItem from "@/components/AttendanceRequestItem.vue"
import ShiftRequestItem from "@/components/ShiftRequestItem.vue"
import ShiftAssignmentItem from "@/components/ShiftAssignmentItem.vue"
import LeaveRequestItem from "@/components/LeaveRequestItem.vue"
import ExpenseClaimItem from "@/components/ExpenseClaimItem.vue"
import EmployeeAdvanceItem from "@/components/EmployeeAdvanceItem.vue"
import ListFiltersActionSheet from "@/components/ListFiltersActionSheet.vue"
import CustomIonModal from "@/components/CustomIonModal.vue"
import RequestActionSheet from "@/components/RequestActionSheet.vue"
import { EMPLOYEE_CHECKIN_FIELDS } from "@/data/config/requestSummaryFields"

import useWorkflow from "@/composables/workflow"
import { useListUpdate } from "@/composables/realtime"

const __ = inject("$translate")
const props = defineProps({
	doctype: {
		type: String,
		required: true,
	},
	fields: {
		type: Array,
		required: true,
	},
	groupBy: {
		type: String,
		required: false,
	},
	filterConfig: {
		type: Array,
		required: true,
	},
	tabButtons: {
		type: Array,
		required: false,
	},
	pageTitle: {
		type: String,
		required: true,
	},
	// newest first by default; `name` breaks ties so pages never repeat or skip a row
	orderBy: {
		type: String,
		required: false,
	},
})

const getButtonKey = (tab) => tab?.key ?? tab

const listItemComponent = {
	"Employee Checkin": markRaw(EmployeeCheckinItem),
	"Attendance Request": markRaw(AttendanceRequestItem),
	"Shift Request": markRaw(ShiftRequestItem),
	"Shift Assignment": markRaw(ShiftAssignmentItem),
	"Leave Application": markRaw(LeaveRequestItem),
	"Expense Claim": markRaw(ExpenseClaimItem),
	"Employee Advance": markRaw(EmployeeAdvanceItem),
}

const router = useRouter()
const dayjs = inject("$dayjs")
const socket = inject("$socket")
const employee = inject("$employee")
const filterMap = reactive({})
// what the filter sheet edits; copied into filterMap only on Apply
const draftFilters = reactive({})
const activeTab = ref(props.tabButtons ? getButtonKey(props.tabButtons[0]) : undefined)
const areFiltersApplied = ref(false)
const appliedFilters = ref([])
const workflowStateField = ref(null)
const isRequestModalOpen = ref(false)
const selectedRequest = ref(null)

// infinite scroll
const scrollContainer = ref(null)
const hasNextPage = ref(true)
const PAGE_LENGTH = 50
const rows = ref([])
const loading = ref(false)
const fetched = ref(false)
// each request gets a number; answers to an older request (another tab, filter or page) are dropped
let requestId = 0

// computed properties
const isTeamRequest = computed(() => {
	return props.tabButtons && activeTab.value === getButtonKey(props.tabButtons[1])
})

const formViewRoute = computed(() => {
	return `${props.doctype.replace(/\s+/g, "")}FormView`
})

const detailViewRoute = computed(() => {
	return `${props.doctype.replace(/\s+/g, "")}DetailView`
})

const defaultFilters = computed(() => {
	const filters = []

	if (isTeamRequest.value) {
		filters.push([props.doctype, "employee", "!=", employee.data.name])
	} else {
		filters.push([props.doctype, "employee", "=", employee.data.name])
	}

	return filters
})

// resources
const createPermission = createResource({
	url: "frappe.client.has_permission",
	params: { doctype: props.doctype, docname: "", perm_type: "create" },
	auto: true,
})

// helper functions
const openRequestModal = async (request) => {
	selectedRequest.value = request
	selectedRequest.value.doctype = "Employee Checkin"
	selectedRequest.value.date = request.time
	selectedRequest.value.formatted_time = dayjs(request.time).format("HH:mm a")
	selectedRequest.value.formatted_latitude = `${Number(request.latitude).toFixed(5)}°`
	selectedRequest.value.formatted_longitude = `${Number(request.longitude).toFixed(5)}°`
	isRequestModalOpen.value = true
}

const closeRequestModal = async () => {
	isRequestModalOpen.value = false
	selectedRequest.value = null
}

function emptyFilters() {
	return Object.fromEntries(
		props.filterConfig.map((filter) => [filter.fieldname, { condition: "=", value: null }])
	)
}

function initializeFilters() {
	Object.assign(filterMap, emptyFilters())
	Object.assign(draftFilters, emptyFilters())
	appliedFilters.value = []
}
initializeFilters()

function prepareFilters() {
	let condition = ""
	let value = ""
	appliedFilters.value = []

	for (const fieldname in filterMap) {
		condition = filterMap[fieldname].condition
		// accessing .value because autocomplete returns an object instead of value
		if (typeof condition === "object" && condition !== null) {
			condition = condition.value
		}

		value = filterMap[fieldname].value
		if (condition && value) appliedFilters.value.push([props.doctype, fieldname, condition, value])
	}
}

// the sheet opens on what is applied, not on edits that were closed without Apply
function resetDraftFilters() {
	for (const fieldname in filterMap) {
		draftFilters[fieldname] = { ...filterMap[fieldname] }
	}
}

function applyFilters() {
	for (const fieldname in draftFilters) {
		filterMap[fieldname] = { ...draftFilters[fieldname] }
	}
	prepareFilters()
	fetchDocumentList()
	modalController.dismiss()
	areFiltersApplied.value = appliedFilters.value.length ? true : false
}

function clearFilters() {
	initializeFilters()
	fetchDocumentList()
	modalController.dismiss()
	areFiltersApplied.value = false
}

const fields = computed(() =>
	workflowStateField.value && !props.fields.includes(workflowStateField.value)
		? [...props.fields, workflowStateField.value]
		: props.fields
)

function toDocs(data) {
	// an empty page comes back as [] instead of { keys, values } (and [] has .keys/.values methods)
	if (!Array.isArray(data?.values)) return []
	return data.values.map((value) => Object.fromEntries(data.keys.map((field, index) => [field, value[index]])))
}

async function fetchDocumentList(start = 0) {
	const id = ++requestId
	if (start === 0) hasNextPage.value = true

	const filters = [[props.doctype, "docstatus", "!=", "2"]]
	filters.push(...defaultFilters.value)
	if (appliedFilters.value) filters.push(...appliedFilters.value)

	loading.value = true
	try {
		const data = await call("frappe.desk.reportview.get", {
			doctype: props.doctype,
			fields: fields.value,
			group_by: props.groupBy,
			order_by: props.orderBy || `\`tab${props.doctype}\`.modified desc, \`tab${props.doctype}\`.name desc`,
			page_length: PAGE_LENGTH,
			start,
			filters,
		})
		if (id !== requestId) return
		const docs = toDocs(data)
		rows.value = start ? rows.value.concat(docs) : docs
		if (docs.length < PAGE_LENGTH) hasNextPage.value = false
	} catch (error) {
		if (id !== requestId) return
		hasNextPage.value = false
		throw error
	} finally {
		if (id === requestId) {
			loading.value = false
			fetched.value = true
		}
	}
}

const handleScroll = debounce(() => {
	if (!hasNextPage.value || loading.value) return

	const { scrollTop, scrollHeight, clientHeight } = scrollContainer.value
	const scrollPercentage = (scrollTop / (scrollHeight - clientHeight)) * 100

	if (scrollPercentage >= 90) {
		fetchDocumentList(rows.value.length)
	}
}, 500)

const handleRefresh = (event) => {
	setTimeout(() => {
		fetchDocumentList()
		event.target.complete()
	}, 500)
}

watch(
	() => activeTab.value,
	(_value) => {
		fetchDocumentList()
	}
)

let stopListUpdates = null
onBeforeUnmount(() => stopListUpdates?.())

onMounted(async () => {
	const workflow = useWorkflow(props.doctype)
	await workflow.workflowDoc.promise
	workflowStateField.value = workflow.getWorkflowStateField()
	fetchDocumentList()

	// someone else's change reloads the first page only when it would show or the user is on it;
	// otherwise the user would be thrown back to the top while scrolling
	stopListUpdates = useListUpdate(socket, props.doctype, (name) => {
		if (rows.value.length <= PAGE_LENGTH || rows.value.some((row) => row.name === name)) {
			fetchDocumentList()
		}
	})
})
</script>

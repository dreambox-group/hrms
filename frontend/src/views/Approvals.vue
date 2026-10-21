<template>
	<BaseLayout :pageTitle="__('Approvals')">
		<template #body>
			<div class="flex flex-col gap-4 p-4 pb-24 w-full">
				<router-link :to="{ name: 'Home' }" class="flex flex-row items-center gap-1 text-sm text-gray-600">
					<FeatherIcon name="chevron-left" class="h-4 w-4" />
					{{ __("Home") }}
				</router-link>
				<h3 class="text-base font-semibold text-gray-900">{{ __("Leave waiting for your approval") }}</h3>
				<LeaveApprovals layout="cards" />
				<OtherApprovals />
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"
import { FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import LeaveApprovals from "@/components/LeaveApprovals.vue"
import OtherApprovals from "@/components/OtherApprovals.vue"

import { homeData } from "@/data/home"

const __ = inject("$translate")

homeData.reload()
onIonViewWillEnter(() => homeData.reload())
</script>

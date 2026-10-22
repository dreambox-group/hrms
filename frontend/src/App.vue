<template>
	<ion-app>
		<ion-router-outlet id="main-content" />
		<!-- the leave request side panel, opened from any page on wide screens -->
		<LeaveRequestPanel v-if="leaveRequestOpen" />
		<Toasts />
	</ion-app>
</template>

<script setup>
import { defineAsyncComponent, onMounted } from "vue"
import { IonApp, IonRouterOutlet } from "@ionic/vue"

import { Toasts } from "frappe-ui"

import { leaveRequestOpen } from "@/composables/leaveRequest"
import { showNotification } from "@/utils/pushNotifications"

// loaded on first use: its data modules need the signed-in employee
const LeaveRequestPanel = defineAsyncComponent(() => import("@/components/LeaveRequestPanel.vue"))

onMounted(() => {
	window?.frappePushNotification?.onMessage((payload) => {
		showNotification(payload)
	})
})
</script>

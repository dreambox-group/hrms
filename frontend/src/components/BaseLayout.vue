<template>
	<ion-page>
		<ion-header class="ion-no-border">
			<div class="w-full bg-white shadow-sm">
				<div :class="['flex flex-row justify-between items-center p-4 w-full mx-auto', containerClass]">
					<div class="flex flex-row items-center gap-6">
						<h2 class="text-xl font-bold text-gray-900">
							{{ props.pageTitle || __("Frappe HR") }}
						</h2>
						<nav class="hidden lg:flex flex-row items-center gap-1" :aria-label="__('Main')">
							<router-link
								v-for="item in sections"
								:key="item.route"
								:to="item.route"
								:class="[
									'rounded px-3 py-1.5 text-sm',
									route.path.startsWith(item.route)
										? 'bg-gray-100 font-semibold text-gray-900'
										: 'text-gray-600 hover:text-gray-900',
								]"
							>
								{{ item.title }}
							</router-link>
						</nav>
					</div>
					<div class="flex flex-row items-center gap-3 ml-auto">
						<router-link
							:to="{ name: 'Notifications' }"
							v-slot="{ navigate }"
							class="flex flex-col items-center"
						>
							<span class="relative inline-block" @click="navigate">
								<FeatherIcon name="bell" class="h-6 w-6" />
								<span
									v-if="unreadNotificationsCount.data"
									class="absolute top-0 right-0.5 inline-block w-2 h-2 bg-red-600 rounded-full border border-white"
								>
								</span>
							</span>
						</router-link>
						<router-link
							:to="{ name: 'Profile' }"
							class="flex flex-col items-center"
						>
							<Avatar
								:image="user.data.user_image"
								:label="user.data.first_name"
								size="xl"
							/>
						</router-link>
					</div>
				</div>
			</div>
		</ion-header>

		<ion-content class="ion-no-padding">
			<div :class="['flex flex-col h-screen w-full mx-auto', containerClass]">
				<slot name="body"></slot>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonHeader, IonContent, IonPage } from "@ionic/vue"
import { FeatherIcon, Avatar } from "frappe-ui"
import { useRoute } from "vue-router"

import { unreadNotificationsCount } from "@/data/notifications"
import { useMainSections } from "@/utils/navigation"

import { computed, inject } from "vue"

const user = inject("$user")
const __ = inject("$translate")
const route = useRoute()
const sections = useMainSections(__)

const props = defineProps({
	pageTitle: {
		type: String,
		required: false,
		default: "",
	},
	// wide pages (the home page) use more of a desktop screen
	wide: {
		type: Boolean,
		default: false,
	},
})

const containerClass = computed(() => (props.wide ? "sm:max-w-6xl" : "sm:max-w-3xl"))
</script>

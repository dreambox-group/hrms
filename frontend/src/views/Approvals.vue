<template>
	<BaseLayout :pageTitle="__('To do')" :backTo="{ name: 'Home' }" :backLabel="__('Home')">
		<template #body>
			<div class="flex w-full flex-col gap-4 px-4 pb-24 pt-4 lg:px-6">
				<TodoList />
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"

import BaseLayout from "@/components/BaseLayout.vue"
import TodoList from "@/components/TodoList.vue"

import { homeData } from "@/data/home"

const __ = inject("$translate")

homeData.reload()
onIonViewWillEnter(() => homeData.reload())
</script>

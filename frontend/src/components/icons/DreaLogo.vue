<template>
	<!-- the Dreambox mark; the name is always written next to it -->
	<img :src="LOGO" alt="" class="object-contain" />
</template>

<script setup>
// served by the hrms app, not bundled
const LOGO = "/assets/hrms/images/drea-hris-logo.png"
</script>

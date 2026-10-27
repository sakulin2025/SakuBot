<script setup lang="ts">
import { ref, watch } from "@sakubot/ui";
import People from "./People.vue";
import Connection from "./Connection.vue";
import ExternalReplies from "./ExternalReplies.vue";
const items = [
  { value: "connection", label: "NapCat" },
  { value: "people", label: "人物" },
  { value: "external", label: "外部消息回应" },
];
const saved = sessionStorage.getItem("qq-management-tab");
const tab = ref(
  items.some((item) => item.value === saved) ? saved! : "connection",
);
watch(tab, (value) => sessionStorage.setItem("qq-management-tab", value));
</script>
<template>
  <STabs v-model="tab" :items="items" />
  <div v-show="tab === 'connection'"><Connection /></div>
  <div v-show="tab === 'people'"><People /></div>
  <div v-show="tab === 'external'"><ExternalReplies /></div>
</template>

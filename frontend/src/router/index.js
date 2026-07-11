import { createRouter, createWebHistory } from "vue-router";
import SpeechAssessment from "@/components/SpeechAssessment.vue";
import SpeechRecognition from "@/components/SpeechRecognition.vue";
import SpeechSynthesize from "@/components/SpeechSynthesize.vue";


export const routes = [
  { path: "/", redirect: "/assessment" },
  { path: "/assessment",  component: SpeechAssessment },
  { path: "/recognition", component: SpeechRecognition },
  { path: "/synthesize",  component: SpeechSynthesize }
];

const router = createRouter({
  history: createWebHistory(), // 如需 hash 模式改成 createWebHashHistory()
  routes
});

export default router;

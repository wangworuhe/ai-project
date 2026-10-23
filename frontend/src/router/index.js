import { createRouter, createWebHistory } from "vue-router";
import SpeechAssessment from "@/components/SpeechAssessment.vue";
import SpeechRecognition from "@/components/SpeechRecognition.vue";
import SpeechSynthesize from "@/components/SpeechSynthesize.vue";
import GoogleTts from "@/components/GoogleTts.vue";
import GrammarPractice from "@/components/GrammarPractice.vue";


import LoginPage from "@/components/LoginPage.vue";
import { auth, refreshSession } from "../auth";

export const routes = [
  { path: "/login", component: LoginPage },
  { path: "/", redirect: "/assessment" },
  { path: "/assessment",  component: SpeechAssessment },
  { path: "/recognition", component: SpeechRecognition },
  { path: "/synthesize",  component: SpeechSynthesize },
  { path: "/google-tts", component: GoogleTts },
  { path: "/grammar", component: GrammarPractice }
];

const router = createRouter({
  history: createWebHistory(), // 如需 hash 模式改成 createWebHashHistory()
  routes
});

router.beforeEach(async to => {
  await refreshSession()
  if (!auth.authenticated && to.path !== '/login') return { path: '/login', query: { next: to.fullPath } }
  if (auth.authenticated && to.path === '/login') return '/grammar'
})
window.addEventListener('auth-expired', () => {
  router.replace({ path: '/login', query: { next: router.currentRoute.value.fullPath } })
})
export default router;

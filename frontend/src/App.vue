<template>
  <div id="app">
    <!-- 顶部导航 -->
    <nav class="nav-bar">
      <RouterLink
        v-for="item in navs"
        :key="item.path"
        :to="item.path"
        class="nav-link"
        active-class="active"
      >
        {{ item.label }}
      </RouterLink>
    </nav>

    <!-- 页面容器 -->
    <main class="page-container">
      <RouterView />
    </main>
    <!-- <h1>语音评估 & 语音识别系统</h1> -->
    <!-- <SpeechAssessment />
    <SpeechRecognition /> -->
  </div>
</template>

<script setup>
// import { routes } from "@/router"; // 复用同一个 routes 数组

const navs = [
  { path: "/assessment",  label: "语音评估" },
  { path: "/recognition", label: "语音识别" },
  { path: "/synthesize",   label: "语音合成" } // SpeechSynthesize
];
</script>

<!-- <script>
import SpeechAssessment from "./components/SpeechAssessment.vue";
import SpeechRecognition from "./components/SpeechRecognition.vue";

export default {
  components: {
    SpeechAssessment,
    SpeechRecognition
  }
};
</script> -->


<style scoped>
.nav-bar {
  display: flex;
  justify-content: center; /* 居中导航项 */
  gap: 24px;
  padding: 12px 24px;
  /* background: none;  默认透明即可 */
}

.nav-link {
  color: #000;            /* 黑色字体 */
  text-decoration: none;
  font-weight: 500;
}

.nav-link.active {
  color: #000;            /* 仍保持黑色 */
  border-bottom: 2px solid #3b82f6; /* 高亮下划线可保留，也可改为 #000 */
}

.page-container {
  /* padding: 24px; */
}

</style>
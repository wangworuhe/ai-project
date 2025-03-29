<template>
  <div id="app">
    <!-- <h1>语音评估 & 语音识别系统</h1> -->

    <SpeechAssessment />
    <SpeechRecognition />
  </div>
</template>

<script>
import SpeechAssessment from "./components/SpeechAssessment.vue";
import SpeechRecognition from "./components/SpeechRecognition.vue";

export default {
  components: {
    SpeechAssessment,
    SpeechRecognition
  }
};
</script>

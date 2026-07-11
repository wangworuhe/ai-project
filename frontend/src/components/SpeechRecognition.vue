<template>
    <div class="recognition">
      <h2>语音识别</h2>
      <button @click="startSTT">🎤 语音识别</button>
      <p v-if="recognizedText">结果: {{ recognizedText }}</p>
    </div>
  </template>
  
  <script>
  import api from "@/api";
  
  export default {
    data() {
      return {
        recognizedText: ""
      };
    },
    methods: {
      async startSTT() {
        const res = await api.get("/stt/recognize-mic");
        this.recognizedText = res.data.data.text;
      }
    }
  };
  </script>

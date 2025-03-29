<template>
    <div class="recognition">
      <h2>语音识别</h2>
      <button @click="startSTT">🎤 语音识别</button>
      <p v-if="recognizedText">结果: {{ recognizedText }}</p>
    </div>
  </template>
  
  <script>
  import axios from "axios";
  
  export default {
    data() {
      return {
        recognizedText: ""
      };
    },
    methods: {
      async startSTT() {
        const res = await axios.get("http://127.0.0.1:5000/stt/recognize-mic");
        this.recognizedText = res.data.data.text;
      }
    }
  };
  </script>
  
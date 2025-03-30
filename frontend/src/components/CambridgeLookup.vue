<template>
    <div class="cambridge-card">
      <h3>🔍 查询单词音标（Cambridge）</h3>
      <input
        v-model="word"
        @keydown.enter="fetchPronunciation"
        placeholder="请输入英文单词"
        class="input"
      />
      <button @click="fetchPronunciation" class="btn">查询</button>
  
      <div v-if="loading" class="info">加载中...</div>
  
      <div v-if="error" class="error">❌ {{ error }}</div>
  
      <div v-if="result" class="result">
        <div class="section">
          <h4>🇺🇸 美式发音</h4>
          <div>音标：<span class="ipa">{{ result.us.ipa || '暂无' }}</span></div>
          <audio v-if="result.us.audio" :src="result.us.audio" controls />
        </div>
  
        <div class="section">
          <h4>🇬🇧 英式发音</h4>
          <div>音标：<span class="ipa">{{ result.uk.ipa || '暂无' }}</span></div>
          <audio v-if="result.uk.audio" :src="result.uk.audio" controls />
        </div>
      </div>
    </div>
  </template>
  
<script>
    export default {
      name: 'CambridgeLookup'
    }
</script>

<script setup>
  import { ref } from 'vue'
  import axios from 'axios'
  
  const word = ref('')
  const loading = ref(false)
  const result = ref(null)
  const error = ref('')
  
  const fetchPronunciation = async () => {
    if (!word.value.trim()) return
    loading.value = true
    result.value = null
    error.value = ''
  
    try {
      const res = await axios.get(`/api/cambridge`, {
        params: { word: word.value.trim() }
      })
      result.value = res.data
    } catch (err) {
      error.value = '查询失败或单词不存在'
    } finally {
      loading.value = false
    }
  }
  </script>
  
  <style scoped>
  .cambridge-card {
    border: 1px solid #ccc;
    padding: 16px;
    border-radius: 8px;
    max-width: 500px;
    font-family: sans-serif;
  }
  .input {
    padding: 6px 10px;
    font-size: 16px;
    width: 60%;
    margin-right: 8px;
  }
  .btn {
    padding: 6px 12px;
  }
  .result {
    margin-top: 16px;
  }
  .section {
    margin-bottom: 12px;
  }
  .ipa {
    font-family: monospace;
    font-weight: bold;
  }
  .info {
    color: #666;
  }
  .error {
    color: red;
    font-weight: bold;
  }
</style>
  
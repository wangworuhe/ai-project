<template>
    <div class="cambridge-card">
      <!-- <div class="cambridge-title">单词音标查询</div> -->
      <h3 class="cambridge-title">单词音标查询</h3>
      <input
        v-model="word"
        @keydown.enter="fetchPronunciation"
        placeholder="请输入英文单词"
        class="input"
      />
      <button @click="fetchPronunciation" class="btn">查询</button>
  
      <!-- <div v-if="loading" class="info">加载中...</div> -->
  
      <div v-if="error" class="error">❌ {{ error }}</div>
  
      <div v-if="result" class="result">
        
        <div class="section">
          <div>UK<span class="ipa">/{{ result.uk.ipa || '暂无' }}/</span></div>
          <button
            v-if="result.uk.audio"
            class="play-btn"
            @click="playAudio(result.uk.audio)"
          >
            🔊
          </button>
          <div style="margin-left: 10px;">US<span class="ipa">/{{ result.us.ipa || '暂无' }}/</span></div>
          <button
            v-if="result.us.audio"
            class="play-btn"
            @click="playAudio(result.us.audio)"
          >
            🔊
          </button>
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
  import api from '@/api'
  
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
      const res = await api.get('/cambridge', {
        params: { word: word.value.trim() }
      })
      result.value = res.data
    } catch (err) {
      error.value = '查询失败或单词不存在'
    } finally {
      loading.value = false
    }
  }

  const playAudio = (url) => {
    const audio = new Audio(url)
    audio.play()
  }

  </script>
  
  <style scoped>
  .cambridge-card {
    border: 1px solid #ccc;
    padding: 16px;
    border-radius: 8px;
    max-width: 800px;
    font-family: sans-serif;
    min-height: 150px;
  }
  .cambridge-title {
    margin: 0 0 16px 0;
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
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 12px;
  }
  .ipa {
    margin-left: 8px;
    font-family: 'Courier New', Courier, monospace;
    font-weight: bold;
    color: #1a2550;
  }
  .info {
    color: #666;
  }
  .error {
    color: red;
    font-weight: bold;
  }

  .play-btn {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: #1a2550;
  }

</style>

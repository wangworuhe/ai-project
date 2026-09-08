<template>
  <div class="google-tts">
    <h2>Google 语音合成</h2>
    <p class="hint">使用 Google Translate TTS，需保持可访问 Google 的网络。</p>

    <el-form :model="form" label-width="100px">
      <el-form-item label="待合成文本">
        <el-input v-model="form.text" type="textarea" :rows="6" maxlength="10000" show-word-limit
          placeholder="请输入或粘贴要朗读的文本" />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="语言">
            <el-select v-model="form.lang">
              <el-option label="English" value="en" />
              <el-option label="简体中文" value="zh-CN" />
              <el-option label="繁体中文" value="zh-TW" />
              <el-option label="日语" value="ja" />
              <el-option label="法语" value="fr" />
              <el-option label="德语" value="de" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="英语口音">
            <el-select v-model="form.tld">
              <el-option label="美国" value="com" />
              <el-option label="英国" value="co.uk" />
              <el-option label="澳大利亚" value="com.au" />
              <el-option label="加拿大" value="ca" />
              <el-option label="印度" value="co.in" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="语速">
            <el-switch v-model="form.slow" active-text="慢速" inactive-text="正常" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="onSynthesize">生成语音</el-button>
      </el-form-item>
    </el-form>

    <div v-if="audioUrl" class="audio-player">
      <audio :src="audioUrl" controls />
      <el-button link type="primary" @click="download">下载 MP3</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const form = ref({ text: '', lang: 'en', tld: 'com', slow: false })
const loading = ref(false)
const audioUrl = ref('')

const onSynthesize = async () => {
  if (!form.value.text.trim()) return ElMessage.error('请先输入要合成的文本')
  loading.value = true
  audioUrl.value = ''
  try {
    const { data } = await api.post('/google-tts/synthesize', form.value)
    if (data.status === 'success') audioUrl.value = data.data.file
    else ElMessage.error(data.message || '生成失败')
  } catch (error) {
    ElMessage.error(
      error.response?.data?.message
        || '无法连接服务。请确认 yalamac-mini.tailaafe48.ts.net 已设为代理直连。'
    )
  } finally {
    loading.value = false
  }
}

const download = () => {
  const link = document.createElement('a')
  link.href = audioUrl.value
  link.download = audioUrl.value.split('/').pop()
  link.click()
}
</script>

<style scoped>
.google-tts { max-width: 800px; margin: auto; padding: 24px; }
.hint { color: #606266; margin: 0 0 20px; }
.audio-player { display: flex; align-items: center; gap: 16px; margin-top: 24px; }
.audio-player audio { max-width: 100%; }
</style>

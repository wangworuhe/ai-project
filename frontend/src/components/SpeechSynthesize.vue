<template>
  <div class="speech-synthesis">
    <h2>语音合成 (SpeechSynthesis)</h2>

    <!-- 文本输入 -->
    <el-form :model="form" label-width="100px">
      <el-form-item label="待合成文本">
        <el-input
          type="textarea"
          v-model="form.text"
          placeholder="请输入要合成的文本"
          rows="4"
        />
      </el-form-item>

      <!-- 基础参数 -->
      <el-row :gutter="16">
        <el-col :span="6">
          <el-form-item label="语言 (Locale)">
            <el-select v-model="form.locale" placeholder="选择语言">
              <el-option label="中文 (zh-CN)" value="zh-CN" />
              <el-option label="英文 (en-US)" value="en-US" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="声线 (Voice)">
            <el-select v-model="form.voice" placeholder="选择声线">
              <el-option
                v-for="v in voices"
                :key="v.name"
                :label="v.label"
                :value="v.name"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="风格 (Style)">
            <el-select v-model="form.style" placeholder="选择风格">
              <el-option label="默认" value="" />
              <el-option label="欢快" value="cheerful" />
              <el-option label="悲伤" value="sad" />
              <el-option label="愤怒" value="angry" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="强度 (StyleDegree)">
            <el-input-number v-model="form.styledegree" :min="1" :max="2" />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- Prosody 参数 -->
      <el-row :gutter="16">
        <el-col :span="6">
          <el-form-item label="语速 (Rate)">
            <el-input v-model="form.rate" placeholder="+10%, fast, x-slow 等" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="音调 (Pitch)">
            <el-input v-model="form.pitch" placeholder="+0st, -2st 等" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="音量 (Volume)">
            <el-input v-model="form.volume" placeholder="loud, soft, +6dB" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="角色 (Role)">
            <el-input v-model="form.role" placeholder="assistant, customerService 等" />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 操作按钮 -->
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="onSynthesize">
          试听并合成
        </el-button>
      </el-form-item>
    </el-form>

    <!-- 播放 & 下载 -->
    <div v-if="audioUrl" class="audio-player">
      <audio :src="audioUrl" controls />
      <el-button type="text" @click="download">下载 MP3</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

// 可根据项目需求，未来改为从后端 /voices 接口拉取
const voices = [
  { name: 'zh-CN-XiaoxiaoNeural', label: '中文 小小 (xiaoxiao)' },
  { name: 'en-US-JennyNeural',   label: '英文 Jenny' }
]

const form = ref({
  text: '',
  locale: 'zh-CN',
  voice: 'zh-CN-XiaoxiaoNeural',
  style: '',
  styledegree: 1,
  role: '',
  rate: '',
  pitch: '',
  volume: ''
})

const loading = ref(false)
const audioUrl = ref('')

const onSynthesize = async () => {
  if (!form.value.text.trim()) {
    return ElMessage.error('请先输入要合成的文本')
  }
  loading.value = true
  audioUrl.value = ''
  try {
    const { data } = await axios.post('http://127.0.0.1:5000/tts/synthesize', form.value)
    if (data.status === 'success') {
      // 接口返回的是相对路径
      audioUrl.value = data.data.file
    } else {
      ElMessage.error(data.message || '合成失败')
    }
  } catch (e) {
    ElMessage.error('网络或服务错误')
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
.speech-synthesis {
  max-width: 800px;
  margin: auto;
  padding: 24px;
}
.audio-player {
  margin-top: 24px;
}
</style>

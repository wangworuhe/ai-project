<template>
  <!-- ✅ 按钮绑定：使用 controlButtons 配置渲染按钮 -->
  <div class="assessment-container">
    <div class="global-title">语音评估</div>

    <div class="left-panel">
      <div class="input-section">
        <!-- 输入文本框 -->
        <textarea
          v-model="text"
          @input="autoResize"
          :style="textAreaStyle"
          class="input-box"
          placeholder="请输入评估文本"
        ></textarea>

        <!-- 控制按钮组 -->
        <div class="button-group">
          <button
            v-for="(btn, idx) in controlButtons"
            :key="idx"
            :class="[btn.class, { active: btn.activeCondition?.() }]"
            @click="btn.action"
            :disabled="btn.disabled?.()"
          >
            {{ btn.text() }}
          </button>
        </div>
        <!-- 错误提示信息 -->
        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
      </div>
    </div>

    <div class="right-panel">
      <div v-if="score !== null" class="result-container">
        <!-- 上下布局的上半部 -->
        <div class="visualization-section">
          <!-- 音素级评估 -->
          <div class="text-display">
            <template v-for="(word, index) in processedWords" :key="index">
              <span
                @click="handleWordClick(word, index, $event)"
                :class="[word.errorType, { 'clickable-word': word.Phonemes?.length }]"
                @mouseenter="showPhonemesTooltip(word, $event)"
                @mouseleave="hideTooltip"
              >
                {{ word.Word }}
              </span>
            </template>
          </div>

          <!-- 新增弹窗组件 && currentWordDetails -->
          <div 
            v-if="showPopup" 
            ref="popupEl"
            class="word-popup" 
            :style="popupStyle"
          >
            <!-- 第一部分：单词评分 -->
            <div class="popup-header">
              得分：{{ currentWordDetails.pronunciationScore ?? 'N/A' }}
            </div>
            <!-- 第二部分：音素/音节分栏 -->
            <div class="popup-columns">
              <!-- 音素列 -->
              <div class="phoneme-column">
                <div class="sub-title">音素评估</div>
                <!-- 第一行：音素字母 -->
                <div class="phoneme-letters">
                  <span 
                    v-for="(phoneme, pIdx) in currentWordDetails.phonemes" 
                    :key="pIdx" 
                    class="label"
                    :class="getScoreClass(phoneme.score)"
                  >
                    {{ phoneme.phoneme }}
                  </span>
                </div>
                <!-- 第二行：音素评分 -->
                <div class="phoneme-scores">
                  <span 
                    v-for="(phoneme, pIdx) in currentWordDetails.phonemes" 
                    :key="pIdx" 
                    class="score"
                    :class="getScoreClass(phoneme.score)"
                  >
                    {{ phoneme.score }}
                  </span>
                </div>
              </div>
              <!-- 音节列 -->
              <div class="syllable-column">
                <div class="sub-title">音节评估</div>
                <!-- 第一行：音节内容 -->
                <div class="syllable-letters">
                  <span 
                    v-for="(syllable, sIdx) in currentWordDetails.syllables" 
                    :key="sIdx" 
                    class="label"
                    :class="getScoreClass(syllable.score)"
                  >
                    {{ syllable.syllable }}
                  </span>
                </div>
                <!-- 第二行：音节评分 -->
                <div class="syllable-scores">
                  <span 
                    v-for="(syllable, sIdx) in currentWordDetails.syllables" 
                    :key="sIdx" 
                    class="score"
                    :class="getScoreClass(syllable.score)"
                  >
                    {{ syllable.score }}
                  </span>
                </div>
              </div>
            </div>
            <!-- 第三部分：预留区域 -->
            <div class="reserved-area" style="height: 40px; margin-top: 12px"></div>
          </div>

          <!-- 右：错误类型 -->
          <div class="error-filters-wrapper">
            <div class="error-filters">
              <label v-for="(value, key) in errorFilters" :key="key">
                <input type="checkbox" v-model="errorFilters[key]" />
                {{ getFilterLabel(key) }}
              </label>
            </div>
          </div>
        </div>
        <!-- 上下布局的下半部 -->
        <div class="summary-section">
          <div class="score-summary"  style="display: flex; gap: 20px; flex-wrap: wrap;">
            <p style="margin: 0; min-width: 120px;">发音总分: {{ pron_score }}</p>
            <p style="margin: 0; min-width: 120px;">准确度: {{ accuracy }}</p>
            <p style="margin: 0; min-width: 120px;">流利度: {{ fluency }}</p>
            <p style="margin: 0; min-width: 120px;">完整度: {{ completeness }}</p>
            <p style="margin: 0; min-width: 120px;">韵律评分: {{ prosody_score }}</p>
          </div>
        </div>
      </div>
    </div>

  </div>

  <!-- Cambridge 字典组件 -->
   <!-- 美式音标与发音区域 -->
  <div class="cambridge-section">
    <button @click="showCambridge = !showCambridge" class="query-button">
      {{ showCambridge ? '隐藏发音查询' : '查询音标与发音' }}
    </button>
    <CambridgeLookup v-if="showCambridge" :word="currentWordDetails.word" />
  </div>
</template>

    <!-- 工具提示 tooltip -->
    <transition name="tooltip">
      <div
        v-if="showTooltip"
        class="phoneme-tooltip"
        :style="{ left: `${tooltipPosition.x}px`, top: `${tooltipPosition.y}px` }"
      >
        <div class="tooltip-header">音素得分</div>
        <div v-html="tooltipContent"></div>
      </div>
    </transition>


<script setup>
// 导入依赖
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import axios from 'axios'
import CambridgeLookup from './CambridgeLookup.vue'

// 字典组件
const showCambridge = ref(false)

// 评估输入与结果状态
const text = ref('')                     // 用户输入的文本
const score = ref(null)                  // 综合得分
const pron_score = ref(null)             // 发音评分
const accuracy = ref(null)               // 准确度
const fluency = ref(null)                // 流利度
const completeness = ref(null)           // 完整度
const prosody_score = ref(null)          // 韵律评分

// 单词和详细评估结果
const words = ref([])                    // 每个单词的评估结果
const detailedResult = ref(null)         // 完整评估返回数据

// 音频录音相关
const isEvaluating = ref(false)          // 是否正在评估中
const isPlaying = ref(false)             // 是否正在播放录音
const recording = ref(false)             // 是否正在录音
const mediaRecorder = ref(null)          // MediaRecorder 对象
const audioChunks = ref([])              // 录音块数据
const audioBlob = ref(null)              // 最终音频 Blob
const audioUrl = ref(null)               // 可播放 URL

// 输入框和错误信息
const errorMessage = ref('')             // 错误提示信息
const textareaHeight = ref(50)           // 输入框高度

// 错误筛选器（使用 reactive 对象）
const errorFilters = reactive({
  mispronunciation: true,
  omission: true,
  insertion: true,
  unexpectedBreak: true,
  missingBreak: true,
  monotone: true
})

// 弹窗交互相关
// const expandedIndex = ref(-1)            // 当前展开的单词索引
const showPopup = ref(false)             // 是否显示单词弹窗
const currentWordDetails = ref(null)     // 当前弹窗展示的单词详情
const popupPosition = reactive({ x: 0, y: 0 })
const popupWidth = ref(400)
const popupHeight = ref(160)
const popupEl = ref(null)                // 弹窗 DOM 引用

// Tooltip 提示状态
const showTooltip = ref(false)
const tooltipContent = ref('')
const tooltipPosition = reactive({ x: 0, y: 0 })

// ✅ 第 3 步：迁移 computed 计算属性

// 输入框样式根据文本长度动态调整字号
const textAreaStyle = computed(() => {
  const baseSize = text.value.length > 40 ? 22 : 
                   text.value.length > 30 ? 26 : 28
  return {
    fontSize: `${baseSize}px`,
    lineHeight: `${baseSize * 1.3}px`
  }
})

// 过滤后的单词（用于错误筛选）
const processedWords = computed(() => {
  return (words.value || []).filter(word => {
    if (word.errorType === 'insertion' && !errorFilters.insertion) return false
    return true
  })
})

// 弹窗位置样式（绑定 style）
const popupStyle = computed(() => {
  return {
    left: `${popupPosition.x}px`,
    top: `${popupPosition.y}px`,
    minWidth: `${popupWidth.value}px`,
    minHeight: `${popupHeight.value}px`,
    maxWidth: '650px'
  }
})

// 获取错误类型中文名称
const getFilterLabel = (key) => {
  const labels = {
    mispronunciation: '发音错误',
    omission: '单词缺失',
    insertion: '多余单词',
    unexpectedBreak: '意外停顿',
    missingBreak: '缺少停顿',
    monotone: '单调语音'
  }
  return labels[key] || key
}

// 根据评分数值返回样式类名
const getScoreClass = (score) => {
  const numeric = Number(score)
  if (isNaN(numeric)) return ''
  if (numeric < 60) return 'score-low'
  if (numeric <= 80) return 'score-mid'
  return 'score-high'
}

// ✅ 第 4 步：迁移 methods 到函数写法（含注释）

// 自动调整 textarea 高度
const autoResize = () => {
  nextTick(() => {
    const textarea = document.querySelector('.input-box')
    if (!textarea) return
    textarea.style.height = 'auto'
    const newHeight = Math.min(textarea.scrollHeight + 5, 580)
    textarea.style.height = `${newHeight}px`
    textareaHeight.value = newHeight
  })
}

// 切换录音状态
const toggleRecording = async () => {
  if (recording.value) {
    stopRecording()
  } else {
    await startRecording()
  }
}

// 开始录音
const startRecording = async () => {
  audioChunks.value = []
  audioBlob.value = null
  audioUrl.value = null
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder.value = new MediaRecorder(stream)
    mediaRecorder.value.ondataavailable = event => {
      audioChunks.value.push(event.data)
    }
    mediaRecorder.value.onstop = () => {
      audioBlob.value = new Blob(audioChunks.value, { type: 'audio/webm' })
      audioUrl.value = URL.createObjectURL(audioBlob.value)
    }
    mediaRecorder.value.start()
    recording.value = true
  } catch (err) {
    console.error('麦克风错误', err)
    alert('无法访问麦克风，请检查权限设置。')
  }
}

// 停止录音
const stopRecording = () => {
  if (mediaRecorder.value && recording.value) {
    mediaRecorder.value.stop()
    recording.value = false
    audioBlob.value = new Blob(audioChunks.value, { type: 'audio/webm' })
    audioUrl.value = URL.createObjectURL(audioBlob.value)
  }
}

// 播放录音
const playRecording = () => {
  if (!audioUrl.value) return alert('没有可播放的录音')
  if (isPlaying.value) return
  isPlaying.value = true
  const audio = new Audio(audioUrl.value)
  audio.onended = () => isPlaying.value = false
  audio.play()
}

// 快捷键监听
const handleKeydown = (e) => {
  const tag = e.target.tagName.toLowerCase()
  if (tag === 'input' || tag === 'textarea') return
  if (e.key === 'r' && e.ctrlKey) {
    e.preventDefault()
    playRecording()
  } else if (e.key === 'r') {
    e.preventDefault()
    toggleRecording()
  }
}

// 点击弹窗外部时隐藏弹窗
const handleClickOutside = (event) => {
  if (popupEl.value && !popupEl.value.contains(event.target)) {
    showPopup.value = false
  }
}

// ✅ 第 7 步：功能迁移 - 语音评估主函数 assessSpeech()

// 发起语音评估请求
const assessSpeech = async () => {
  if (!text.value.trim()) {
    errorMessage.value = '请输入文本进行评估'
    return
  }
  if (!audioBlob.value) {
    errorMessage.value = '请先录制语音文件'
    return
  }
  isEvaluating.value = true
  errorMessage.value = ''

  const formData = new FormData()
  formData.append('audio', audioBlob.value, 'recording.wav')
  formData.append('reference_text', text.value)

  try {
    const res = await axios.post('http://127.0.0.1:5000/assessment/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    const data = res.data.data
    score.value = data.pronunciation_score
    pron_score.value = data.pronunciation_score
    accuracy.value = data.accuracy_score
    fluency.value = data.fluency_score
    completeness.value = data.completeness_score
    prosody_score.value = data.prosody_score
    detailedResult.value = data.detailed_result
    const nBest = data.detailed_result?.NBest?.[0] || {}
    words.value = (nBest.Words || []).map(w => ({
      ...w,
      errorType: w.PronunciationAssessment?.ErrorType?.toLowerCase() || 'none'
    }))
  } catch (err) {
    console.error('评估失败', err)
    errorMessage.value = err.response?.data?.message || err.message || '连接失败'
  } finally {
    isEvaluating.value = false
  }
}

// 单词点击展示评分弹窗
const handleWordClick = (word, index, event) => {
  event.stopPropagation()
  if (!word.Phonemes?.length) return

  const rect = event.target.getBoundingClientRect()
  popupPosition.x = rect.left + window.scrollX + rect.width / 2 - popupWidth.value / 2
  popupPosition.y = rect.bottom + window.scrollY + 5

  currentWordDetails.value = {
    pronunciationScore: word.PronunciationAssessment?.AccuracyScore,
    phonemes: word.Phonemes?.map(p => ({
      phoneme: p.Phoneme,
      score: p.PronunciationAssessment?.AccuracyScore ?? 'N/A'
    })) || [],
    syllables: word.Syllables?.map(s => ({
      syllable: s.Syllable,
      score: s.PronunciationAssessment?.AccuracyScore ?? 'N/A'
    })) || []
  }
  showPopup.value = true
}

// ✅ 第 9 步：功能迁移 - 工具提示 Tooltip 相关函数

// 显示音素提示气泡
const showPhonemesTooltip = (word, event) => {
  if (!word.Phonemes) return
  const rect = event.target.getBoundingClientRect()
  tooltipPosition.x = rect.left + window.scrollX
  tooltipPosition.y = rect.top + window.scrollY - 40

  tooltipContent.value = word.Phonemes.map(p => `
    <div class="phoneme-row">
      <span>${p.Phoneme}</span>
      <span style="color: ${getPhonemeColor(p)}">
        ${p.PronunciationAssessment?.AccuracyScore ?? 'N/A'}
      </span>
    </div>
  `).join('')

  showTooltip.value = true
}

// 隐藏提示
const hideTooltip = () => {
  showTooltip.value = false
  tooltipContent.value = ''
}

// 实时更新 tooltip 位置（可选）
// const updateTooltipPosition = (event) => {
//   if (!showTooltip.value) return
//   const rect = event.target.getBoundingClientRect()
//   tooltipPosition.x = rect.left + window.scrollX
//   tooltipPosition.y = rect.top + window.scrollY - 40
// }

// 根据音素得分返回颜色
const getPhonemeColor = (phoneme) => {
  const score = phoneme.PronunciationAssessment?.AccuracyScore
  if (score < 60) return '#dc2626'
  if (score < 80) return '#f4f4f5'
  return '#676769'
}

// ✅ 第 10 步：按钮控制组配置

const controlButtons = [
  {
    class: 'recording-button',
    action: toggleRecording,
    activeCondition: () => recording.value,
    text: () => recording.value ? '⏹ 停止录音 (R)' : '🎤 开始录音 (R)'
  },
  {
    class: 'play-button',
    action: playRecording,
    disabled: () => !audioBlob.value,
    text: () => isPlaying.value ? '🔊 播放中...' : '▶ 播放录音'
  },
  {
    class: 'evaluate-button',
    action: assessSpeech,
    disabled: () => isEvaluating.value || recording.value,
    text: () => isEvaluating.value ? '正在评估...' : '开始语音评估'
  }
]

// ✅ 第 5 步：挂载生命周期事件

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})

</script>

<style >
.global-title {
  position: absolute;
  top: 5px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 24px;
  font-weight: 600;
  z-index: 10;
  padding: 1px 1px;
  border-radius: 8px;
}

.assessment-container {
  position: relative; /* 为绝对定位标题提供参照 */
  display: flex;
  width: 100%;
  padding: 60px 20px 20px; /* 增加顶部内边距 */
  box-sizing: border-box;
}

.left-panel {
  flex: 0.9;
  /* min-width: 50%; 保证最小占50% */
}

.right-panel {
  flex: 1.1;
  min-width: 50%; /* 保证最小占50% */
  min-height: 100%;
  background: inherit; 
}

.input-box {
  width: 85%; 
  min-height: 120px;        /* 默认高度 */
  /*  max-height: 1200px;         /* 适当增加最大高度 */
  margin: 0 20px;           /* 水平边距 */
  font-family: 'Segoe UI', 'Google Sans', Arial, sans-serif; /* 优化字体栈 */
  letter-spacing: 0.2px;   /* 微调字间距 */
  font-weight: 400;         /* 标准字重 */
  padding: 16px 24px;       /* 增加内边距 */
  
  /* 保留原有其他样式 */
  border-radius: 8px;
  box-shadow: 0 1px 6px rgba(32,33,36,.28);
  transition: all 0.3s cubic-bezier(0.4,0.0,0.2,1);
  border: 1px solid #dfe1e5;
  resize: none;
  overflow-y: auto;      /* 隐藏垂直滚动条 */
}

.input-box:focus {
  border-color: #4285f4;
  box-shadow: 0 1px 6px rgba(66,133,244,.28);
}

.button-group {
  margin: 16px 20px;
  display: flex;
  gap: 12px;
  justify-content: flex-start;
  flex-wrap: wrap;
}

.evaluate-btn {
  margin-top: 10px;
  padding: 8px 16px;
  font-size: 16px;
  color: white;
  background-color: #007BFF;
  border: none;
  border-radius: 5px;
  cursor: pointer;
}

.evaluate-btn:hover {
  background-color: #0056b3;
}

.result-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px); /* 根据实际高度调整 */
}

.visualization-section {
  /* flex: 1; */
  display: flex;
  gap: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eee;
}

/* 新增右侧面板样式 */
.score-summary {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-top: auto; /* 确保始终在底部 */
}

.error-message {
  margin-top: 10px;
  color: red;
  font-weight: bold;
}

.evaluate-button {
  padding: 10px 20px;
  background-color: #4CAF50;
  color: white;
  border: none;
  cursor: pointer;
  transition: background-color 0.3s;
}

.evaluate-button:disabled {
  background-color: #9E9E9E;
  cursor: not-allowed;
}

/* 公共按钮样式 */
.button-base {
  padding: 10px 20px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.3s;
  margin: 4px;
}

.recording-button {
  padding: 10px 20px;
  background-color: #ff4d4d;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.3s;
}

/* 按钮状态扩展 */
.recording-button { @apply button-base bg-danger; }
.play-button { @apply button-base bg-primary; }
.evaluate-button { @apply button-base bg-success; }
.recording-button.active {
  background-color: #b30000;
}

.play-button {
  padding: 10px 20px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.play-button.active {
  background-color: #0056b3;
  cursor: not-allowed;
}

.play-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

/* 错误类型样式 */
.mispronunciation {
  background-color: yellow;
}

.omission {
  background-color: gray;
}

.insertion {
  background-color: red;
  text-decoration: line-through;
}

.unexpectedBreak {
  background-color: pink;
}

.missingBreak {
  background-color: lightgray;
}

.monotone {
  background-color: purple;
}

.error-filters {
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  position: sticky;
  top: 20px;
}

.error-filters label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.error-filters label:hover {
  background: rgba(0,0,0,0.05);
}

.summary-section {
  padding-top: 20px;
  margin-top: 20px;
}

.text-display {
  flex: 3;
  min-width: 0;
  background: #fff;
  border-radius: 8px;
  padding: 16px 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  overflow-y: auto;
  position: relative;
  font-family: 'Segoe UI', system-ui, sans-serif;
  line-height: 1.6;
  transition: box-shadow 0.2s ease;
  font-size: 22px;
}

/* 文字内容容器优化 */
.text-display > span {
  display: inline-block;
  margin: 2px;
  padding: 1px 8px;
  transition: 
    transform 0.15s ease,
    background 0.2s ease;
}

/* 悬停效果增强 */
.text-display > span:hover {
  /* transform: translateY(-1px);
  background: rgba(245,245,245,0.8); */
  cursor: pointer;
}

/* 滚动条美化 */
.text-display::-webkit-scrollbar {
  width: 8px;
  background: rgba(245,245,245,0.8);
}

.text-display::-webkit-scrollbar-thumb {
  background: rgba(200,200,200,0.6);
  border-radius: 4px;
}

/* 保持错误类型高亮的层级 */
.text-display > span[class*="word-token"] {
  position: relative;
  z-index: 1;
}

.error-filters-wrapper {
  flex: 1;
  min-width: 150px;
  max-width: 160px;
}


/* 工具提示 */
.phoneme-tooltip {
  position: fixed;
  background: white;
  border: 1px solid #ddd;
  padding: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  z-index: 1000;
}

/* 音素颜色 */
.phoneme-score-low { color: #dc2626; }
.phoneme-score-medium { color: #f4f4f5; }
.phoneme-score-high { color: #676769; }

/* 展开区域 */
.phoneme-details {
  background: rgba(250,250,250,0.9);
  backdrop-filter: blur(2px);
  border-radius: 6px;
  padding: 8px 12px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  margin-top: 6px;
}

.phoneme-details.expanded {
  max-height: 200px;
}

/* 错误类型高亮 */
.word-token.mispronunciation { background: #fff3cd; }
.word-token.omission { 
  background: gray; 
}
.word-token.insertion { background: red; }
.word-token.unexpectedbreak { border-bottom: 2px solid #fecaca; }
.word-token.missingbreak { border-bottom: 2px dashed #d1d5db; }
.word-token.monotone { background: #ede9fe; }

/* 空数据提示 */
.no-data-tip {
  padding: 12px;
  background: #f3f4f6;
  border-radius: 4px;
  color: #6b7280;
}

/* 过渡动画 */
.tooltip-enter-active {
  transition: all 0.2s ease-out;
}

.tooltip-leave-active {
  transition: all 0.1s ease-in;
}

.tooltip-enter-from,
.tooltip-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 调整工具提示层级 */
.phoneme-tooltip {
  z-index: 9999; /* 确保在最顶层 */
  box-shadow: 0 3px 6px rgba(0,0,0,0.16); /* 添加阴影提升立体感 */
}

/* 可点击单词样式 */
.clickable-word {
  cursor: pointer;
  transition: transform 0.1s;
}
.clickable-word:active {
  transform: scale(0.95);
}

.word-popup {
  position: absolute;
  background: white;
  border: 2px solid #007bff;
  border-radius: 5px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  padding: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  white-space: normal;
  z-index: 1000;
}

/* 分栏布局 */
.popup-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-top: 12px;
}

/* 统一评分项样式 */
.phoneme-row,
.syllable-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid #f0f0f0;
}

.sub-title {
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 2px solid #007bff;
}

/* 使音素/音节内容横向排列，并在垂直方向对齐 */
.phoneme-letters,
.phoneme-scores,
.syllable-letters,
.syllable-scores {
  display: flex;
  flex-direction: row;
  /* gap: 1px; /* 根据需要调整间距 */
}

/* 让字母和评分都居中对齐 */
.phoneme-letters .label,
.syllable-letters .label{
  display: inline-block;
  text-align: center;
  min-width: 30px; /* 可根据实际情况调整宽度，保证对齐 */
}

.phoneme-scores .score,
.syllable-scores .score {
  font-size: 0.85em;
  display: inline-block;
  text-align: center;
  min-width: 30px; /* 可根据实际情况调整宽度，保证对齐 */
}

/* 预留区域样式 */
.reserved-area {
  border: 1px dashed #ddd;
  border-radius: 4px;
}

/* 评分颜色 */
.score-low {
  color: #dc2626;
}
.score-mid {
  color: #ca8a04;
}
.score-high {
  color: #4f4f51;
}
</style>
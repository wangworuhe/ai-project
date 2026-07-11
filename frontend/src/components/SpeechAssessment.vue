<template>
  <!-- ✅ 按钮绑定：使用 controlButtons 配置渲染按钮 -->
  <div :class="style['assessment-container']">
    <!-- <div :class="style['global-title']">语音评估</div> -->

    <div :class="style['left-panel']">
      <div :class="style['input-section']">
        <!-- 输入文本框 -->
        <textarea
          ref="textareaRef"
          v-model="text"
          @input="autoResize"
          :style="textAreaStyle"
          :class="style['input-box']"
          placeholder="请输入评估文本"
        ></textarea>

        <!-- 控制按钮组 -->
        <div :class="style['button-group']">
          <button
            v-for="(btn, idx) in controlButtons"
            :key="idx"
            :class="[style[btn.class], { [style.active]: btn.activeCondition?.() }]"
            @click="btn.action"
            :disabled="btn.disabled?.()"
          >
            {{ btn.text() }}
          </button>
        </div>
        <!-- 错误提示信息 -->
        <p v-if="errorMessage" :class="style['error-message']">{{ errorMessage }}</p>
      </div>
    </div>

    <div :class="style['right-panel']">
      <div v-if="score !== null" :class="style['result-container']">
        <!-- 上下布局的上半部 -->
        <div :class="style['visualization-section']">
          <!-- 音素级评估 -->
          <div :class="style['text-display']">
            <template v-for="(word, index) in processedWords" :key="index">
              <span
                @click="handleWordClick(word, index, $event)"
                :class="[
                  // 动态绑定样式类，根据 showStyle 决定是否显示错误样式
                  word.showStyle ? style[word.errorType] : '',
                  { 
                    [style['clickable-word']]: word.Phonemes?.length,
                    // 添加默认样式用于覆盖
                    [style['word-default']]: !word.showStyle
                  }
                ]"
              >
                {{ word.Word }}
              </span>
            </template>
          </div>

          <!-- 新增弹窗组件 && currentWordDetails -->
          <div 
            v-if="showPopup" 
            ref="popupEl"
            :class="style['word-popup']" 
            :style="popupStyle"
          >
            <!-- 第一部分：单词评分 -->
            <div :class="style['popup-header']">
              得分：{{ currentWordDetails.pronunciationScore ?? 'N/A' }}
            </div>
            <!-- 第二部分：音素/音节分栏 -->
            <div :class="style['popup-columns']">
              <!-- 音素列 -->
              <div :class="style['phoneme-column']">
                <div :class="style['sub-title']">音素评估</div>
                <!-- 第一行：音素字母 -->
                <div :class="style['phoneme-letters']">
                  <span 
                    v-for="(phoneme, pIdx) in currentWordDetails.phonemes" 
                    :key="pIdx" 
                    :class="[style.label, style[getScoreClass(phoneme.score)]]"
                  >
                    {{ phoneme.phoneme }}
                  </span>
                </div>
                <!-- 第二行：音素评分 -->
                <div :class="style['phoneme-scores']">
                  <span 
                    v-for="(phoneme, pIdx) in currentWordDetails.phonemes" 
                    :key="pIdx" 
                    :class="[style.score, style[getScoreClass(phoneme.score)]]"
                  >
                    {{ phoneme.score }}
                  </span>
                </div>
              </div>
              <!-- 音节列 -->
              <div :class="style['syllable-column']">
                <div :class="style['sub-title']">音节评估</div>
                <!-- 第一行：音节内容 -->
                <div :class="style['syllable-letters']">
                  <span 
                    v-for="(syllable, sIdx) in currentWordDetails.syllables" 
                    :key="sIdx" 
                    :class="[style.label, style[getScoreClass(syllable.score)]]"
                  >
                    {{ syllable.syllable }}
                  </span>
                </div>
                <!-- 第二行：音节评分 -->
                <div :class="style['syllable-scores']">
                  <span 
                    v-for="(syllable, sIdx) in currentWordDetails.syllables" 
                    :key="sIdx" 
                    :class="[style.score, style[getScoreClass(syllable.score)]]"
                  >
                    {{ syllable.score }}
                  </span>
                </div>
              </div>
            </div>
            <!-- 第三部分：预留区域 -->
            <div :class="style['reserved-area']"></div>
          </div>

          <!-- 右：错误类型 -->
          <div :class="style['error-filters-wrapper']">
            <div :class="style['error-filters']">
              <label
                v-for="(value, key) in errorFilters"
                :key="key"
                :class="style['filter-row']"
              >
                <!-- 左：计数块 -->
                <div :class="[style['filter-count'], style[key + '-count']]">
                  {{ errorCounts[key] || 0 }}
                </div>

                <!-- 中：文字标签 + info 图标 -->
                <div :class="style['filter-label']">
                  {{ getFilterLabel(key) }}
                </div>

                <!-- 右：开关 -->
                <div :class="style['filter-toggle']">
                  <input type="checkbox" v-model="errorFilters[key]" />
                </div>
              </label>
              <!-- <label v-for="(value, key) in errorFilters" :key="key">
                <input type="checkbox" v-model="errorFilters[key]" />
                {{ getFilterLabel(key) }}
              </label> -->
            </div>
          </div>

        </div>

        <!-- 上下布局的下半部 -->
        <div :class="style['summary-section']">
          <div :class="style['score-summary']">
            <!-- 左侧环形图 -->
            <div :class="style['score-ring']">
              <svg viewBox="0 0 36 36" :class="style['circular-chart']">
                <!-- 背景轨道 -->
                <path 
                  :class="style['circle-bg']"
                  d="M18 2.0845
                     a 15.9155 15.9155 0 0 1 0 31.831
                     a 15.9155 15.9155 0 0 1 0 -31.831"/>
                
                <!-- 进度轨道 -->
                <path
                  :class="style['circle-progress']"
                  :stroke="getScoreColor(pron_score)"
                  :stroke-dasharray="`${pron_score}, 100`"
                  d="M18 2.0845
                     a 15.9155 15.9155 0 0 1 0 31.831
                     a 15.9155 15.9155 0 0 1 0 -31.831"/>

                <text 
                  x="18" 
                  y="14" 
                  :class="style['score-label']"
                  dominant-baseline="middle" 
                  text-anchor="middle">
                  总分
                </text>
                
                <!-- 中心分数显示 -->
                <text 
                  x="18" 
                  y="23" 
                  :class="style['score-value']"
                  dominant-baseline="middle" 
                  text-anchor="middle">
                  {{ pron_score }}
                </text>
              </svg>
              <!-- 底部标签 -->
              <!-- <div :class="style['ring-label']">发音总分</div> -->
            </div>
        
            <!-- 右侧条形图 -->
            <div :class="style['bars-container']">
              <div :class="style['bar-column']">
                <!-- 上方两个 -->
                <div :class="style['bar-item']">
                  <div :class="style['bar-header']">
                    <label>准确度</label>
                    <span :class="style['bar-score']">{{ accuracy }}</span>
                  </div>
                  <div :class="style['bar-bg']">
                    <div
                      :class="style['bar-fill']"
                      :style="{ width: accuracy + '%', backgroundColor: getScoreColor(accuracy) }"
                    ></div>
                  </div>
                </div>
                
                <div :class="style['bar-item']">
                  <div :class="style['bar-header']">
                    <label>流利度</label>
                    <span :class="style['bar-score']">{{ fluency }}</span>
                  </div>
                  <div :class="style['bar-bg']">
                    <div
                      :class="style['bar-fill']"
                      :style="{ width: fluency + '%', backgroundColor: getScoreColor(fluency) }"
                    ></div>
                  </div>
                </div>
                
                <!-- 下方两个 -->
                <div :class="style['bar-item']">
                  <div :class="style['bar-header']">
                    <label>完整度</label>
                    <span :class="style['bar-score']">{{ completeness }}</span>
                  </div>
                  <div :class="style['bar-bg']">
                    <div
                      :class="style['bar-fill']"
                      :style="{ width: completeness + '%', backgroundColor: getScoreColor(completeness) }"
                    ></div>
                  </div>
                </div>
                
                <div :class="style['bar-item']">
                  <div :class="style['bar-header']">
                    <label>韵律评分</label>
                    <span :class="style['bar-score']">{{ prosody_score }}</span>
                  </div>
                  <div :class="style['bar-bg']">
                    <div
                      :class="style['bar-fill']"
                      :style="{ width: prosody_score + '%', backgroundColor: getScoreColor(prosody_score) }"
                    ></div>
                  </div>
                </div>

              </div>
            </div>
            
          </div>
        </div>

      </div>
    </div>
  </div>

  <div class="card-ui">
    <div :class="style['cambridge-dictionary']">
      <CambridgeLookup />
    </div>
    <div :class="style['google-translate-api']">
      <GoogleTranslateAPI />
    </div>
  </div>

</template>

<script setup>
// 导入依赖
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import axios from 'axios'
import style from '../assets/css/SpeechAssessment.module.css'
import CambridgeLookup from './CambridgeLookup.vue'
import GoogleTranslateAPI from './GoogleTranslateAPI.vue'

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

// 输入文本与高度控制
// const inputText = ref('')
const textareaRef = ref(null)
const textareaHeight = ref(120)         // 输入框高度

// 错误信息
const errorMessage = ref('')             // 错误提示信息

// 自动增高逻辑
const autoResize = () => {
  nextTick(() => {
    const textarea = textareaRef.value
    if (!textarea) return
    textarea.style.height = 'auto'
    const newHeight = Math.min(textarea.scrollHeight, 580)  // ✅ 不加余量，真实高度
    textarea.style.height = `${newHeight}px`
    textareaHeight.value = newHeight
  })
}

// 错误筛选器（使用 reactive 对象）
const errorFilters = reactive({
  mispronunciation: true,
  omission: true,
  insertion: true,
  unexpectedbreak: true,
  missingbreak: true,
  monotone: true
})

const errorCounts = ref({
  mispronunciation: 0,
  omission: 0,
  insertion: 0,
  unexpectedbreak: 0,
  missingbreak: 0,
  monotone: 0,
})

// 2. 定义更新方法
const updateErrorCounts = (words) => {
  Object.keys(errorCounts.value).forEach(key => errorCounts.value[key] = 0)

  words.forEach(word => {
    // 处理单词级别错误
    const mainError = word.errorType === 'none' ? null : word.errorType
    if (mainError) {
      const errorKey = mainError.toLowerCase()
      if (Object.prototype.hasOwnProperty.call(errorCounts.value, errorKey)) {
        errorCounts.value[errorKey] += 1
      }
    }

    // 处理韵律错误
    const prosodyErrors = word.PronunciationAssessment?.Feedback?.Prosody
    if (prosodyErrors) {
      // 语调错误
      if (prosodyErrors.Intonation?.ErrorTypes?.includes('Monotone')) {
        errorCounts.value.monotone += 1
      }

      // 停顿错误
      const breakErrors = prosodyErrors.Break?.ErrorTypes || []
      breakErrors.forEach(error => {
        const errorKey = error.replace(/([a-z])([A-Z])/g, '$1$2').toLowerCase()
        if (Object.prototype.hasOwnProperty.call(errorCounts.value, errorKey)) {
          errorCounts.value[errorKey] += 1
        }
      })
    }
  })
}

// 弹窗交互相关
const showPopup = ref(false)             // 是否显示单词弹窗
const currentWordDetails = ref(null)     // 当前弹窗展示的单词详情
const popupPosition = reactive({ x: 0, y: 0 })
const popupWidth = ref(400)
const popupHeight = ref(160)
const popupEl = ref(null)                // 弹窗 DOM 引用

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
    // 特殊处理 insertion 类型
    if (word.errorType === 'insertion') {
      return errorFilters.insertion // 直接根据开关决定显示/隐藏
    }
    return true
  }).map(word => {
    // 对非 insertion 类型添加可见性标记
    return {
      ...word,
      // 添加是否显示样式的标记
      showStyle: errorFilters[word.errorType]
    }
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
    unexpectedbreak: '意外停顿',
    missingbreak: '缺少停顿',
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

// 根据音素得分返回颜色
const getScoreColor = (score) => {
  if (score < 60) return '#ef4444'     // 红色
  if (score < 80) return '#ca8a04'     // 黄色
  return '#22c55e'                     // 绿色
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
    updateErrorCounts(words.value)  // 更新错误计数器
    console.log("words.value:", words.value)
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

onMounted(() => {
  autoResize()
  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})

</script>

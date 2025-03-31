<template>
  <div class="translate-container">
    <!-- 语言选择栏 -->
    <div class="language-tabs">
      <div class="language-selector">
        <select v-model="sourceLanguage" class="language-dropdown">
          <option v-for="lang in languages" :key="'src-'+lang.code" :value="lang.code">
            {{ lang.name }}
          </option>
        </select>
        <span class="separator">→</span>
        <select v-model="targetLanguage" class="language-dropdown">
          <option v-for="lang in languages" :key="'tgt-'+lang.code" :value="lang.code">
            {{ lang.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- 双栏输入输出区域 -->
    <div class="translation-panels">
      <!-- 输入区域 -->
      <div class="input-panel">
        <textarea 
          v-model="sourceText" 
          :placeholder="inputPlaceholder"
          @input="handleInput"></textarea>
        <div class="panel-footer">
          <span class="char-count">{{ sourceText.length }}/5000</span>
          <button class="voice-btn" @click="speakSource">
            <svg width="20" height="20" viewBox="0 0 24 24">
              <path fill="#70757A" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- 输出区域 -->
      <div class="output-panel">
        <div class="translated-text" v-if="translatedText">
          {{ translatedText }}
        </div>
        <div class="placeholder" v-else>
          {{ outputPlaceholder }}
        </div>
        <div class="panel-footer">
          <button class="voice-btn" @click="speakTranslated">
            <svg width="20" height="20" viewBox="0 0 24 24">
              <path fill="#70757A" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
            </svg>
          </button>
          <button class="copy-btn" @click="copyTranslation">
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#70757A" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import { debounce } from 'lodash'

// 修复 ESLint 错误：确保所有定义的变量都被使用
const languages = ref([
  { code: 'zh-CN', name: '简体中文' },
  { code: 'en', name: 'English' },
  { code: 'ja', name: '日本語' },
  { code: 'ko', name: '한국어' }
])

const sourceText = ref('')
const translatedText = ref('')
const sourceLanguage = ref('en')
const targetLanguage = ref('zh-CN')

// 计算属性确保 languages 被使用
// const displayedLanguages = computed(() => [
//   languages.value.find(l => l.code === sourceLanguage.value),
//   languages.value.find(l => l.code === targetLanguage.value)
// ].filter(Boolean))

const inputPlaceholder = computed(() => {
  const lang = languages.value.find(l => l.code === sourceLanguage.value)
  return lang ? `用${lang.name}输入...` : '输入文本...'
})

const outputPlaceholder = computed(() => {
  const lang = languages.value.find(l => l.code === targetLanguage.value)
  return lang ? `将翻译为${lang.name}` : '翻译结果...'
})

// const isActiveLanguage = (code) => 
//   code === sourceLanguage.value || code === targetLanguage.value

// const setLanguage = (code) => {
//   if (code === sourceLanguage.value) return
//   if (code === targetLanguage.value) {
//     swapLanguages()
//   } else {
//     targetLanguage.value = code
//   }
// }

// 其余函数保持不变...
const translateText = debounce(async () => {
  if (!sourceText.value.trim()) {
    translatedText.value = ''
    return
  }
  
  try {
    const encodedText = encodeURIComponent(sourceText.value)
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=${sourceLanguage.value}&tl=${targetLanguage.value}&dt=t&q=${encodedText}`
    const response = await axios.get(url)
    if (Array.isArray(response.data) && response.data[0]) {
      let result = ''
      response.data[0].forEach(translation => {
        if (translation[0]) {
          result += translation[0]
        }
      })
      translatedText.value = result
    } else {
      throw new Error('Invalid response format')
    }
  } catch (error) {
    console.error('Translation error:', error)
    translatedText.value = '翻译出错，请重试'
  }
}, 500)

watch([sourceText, sourceLanguage, targetLanguage], translateText)

// const swapLanguages = () => {
//   [sourceLanguage.value, targetLanguage.value] = [targetLanguage.value, sourceLanguage.value]
//   if (translatedText.value) {
//     [sourceText.value, translatedText.value] = [translatedText.value, sourceText.value]
//   }
// }

const speak = (text, lang) => {
  if ('speechSynthesis' in window) {
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang === 'zh-CN' ? 'zh-CN' : lang === 'en' ? 'en-US' : lang
    utterance.rate = 0.9
    window.speechSynthesis.speak(utterance)
  }
}

const speakSource = () => speak(sourceText.value, sourceLanguage.value)
const speakTranslated = () => speak(translatedText.value, targetLanguage.value)

const copyTranslation = async () => {
  if (!translatedText.value) return
  try {
    await navigator.clipboard.writeText(translatedText.value)
    alert('已复制到剪贴板')
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}

const handleInput = () => {
  const textarea = document.querySelector('.input-panel textarea')
  textarea.style.height = 'auto'
  textarea.style.height = `${textarea.scrollHeight}px`
}
</script>

<style scoped>

.language-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.language-dropdown {
  padding: 8px 12px;
  border: 1px solid #DADCE0;
  border-radius: 4px;
  font-size: 14px;
  color: #202124;
  background-color: white;
}

.separator {
  color: #5F6368;
  font-size: 16px;
}

/* 保持之前的样式不变 */
.translate-container {
  width: 800px;
  margin: 0 auto;
  font-family: 'Roboto', 'Noto Sans SC', sans-serif;
}

.language-tabs {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #E0E0EF;
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.language-tab {
  padding: 8px 16px;
  cursor: pointer;
  color: #5F6368;
  font-size: 14px;
  position: relative;
  transition: all 0.2s;
}

.language-tab.active {
  color: #4285F4;
  font-weight: 500;
}

.language-tab.active::after {
  content: '';
  position: absolute;
  bottom: -9px;
  left: 0;
  width: 100%;
  height: 2px;
  background: #4285F4;
}

.language-swap {
  padding: 0 12px;
  cursor: pointer;
  transition: transform 0.3s;
}

.language-swap:hover {
  transform: rotate(180deg);
}

.translation-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.input-panel, .output-panel {
  border: 1px solid #DADCE0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  height: 200px;
  overflow: hidden;
}

textarea {
  flex-grow: 1;
  padding: 16px;
  border: none;
  resize: none;
  font-size: 16px;
  line-height: 1.5;
  outline: none;
  font-family: inherit;
}

.translated-text, .placeholder {
  flex-grow: 1;
  padding: 16px;
  color: #202124;
  white-space: pre-wrap;
}

.placeholder {
  color: #9AA0A6;
  font-style: italic;
}

.panel-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-top: 1px solid #F1F3F4;
  background: #F8F9FA;
}

.char-count {
  font-size: 12px;
  color: #9AA0A6;
}

.voice-btn, .copy-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.voice-btn:hover, .copy-btn:hover {
  opacity: 1;
}

@media (max-width: 840px) {
  .translate-container {
    width: 100%;
    padding: 0 12px;
  }
  
  .translation-panels {
    grid-template-columns: 1fr;
  }
  
  .input-panel, .output-panel {
    height: 160px;
  }
}
</style>
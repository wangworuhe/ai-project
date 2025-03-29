<template>
  <div class="assessment-container">
    <div class="global-title">语音评估</div>

    <div class="left-panel">
      <!-- 输入区域 -->
      <div class="input-section">
        <textarea 
          v-model="text" 
          @input="autoResize"
          :style="textAreaStyle" 
          class="input-box"
          placeholder="输入文本进行评估..."
        ></textarea>

        <!-- 操作按钮组 -->
        <div class="button-group">
          <button 
            v-for="(btn, idx) in controlButtons" 
            :key="idx"
            @click="btn.action"
            :disabled="btn.disabled?.(this)"
            :class="[
              btn.class, 
              { active: btn.activeCondition?.(this) }
            ]"
          >
            {{ btn.text(this) }}
          </button>
        </div>
        <!-- 显示错误信息 -->
        <br />
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
                :class="[shouldHighlight(word.errorType), { 'clickable-word': word.Phonemes?.length }]"
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
</template>
<transition name="tooltip">
  <div 
    v-if="showTooltip"
    class="phoneme-tooltip"
    :style="{
      left: `${tooltipPosition.x}px`,
      top: `${tooltipPosition.y}px`
    }"
  >
    <div class="tooltip-header">音素得分</div>
    <div v-html="tooltipContent"></div>
  </div>
</transition>

<script>
import axios from "axios";

export default {
  computed: {
    textAreaStyle() {
      const baseSize = this.text.length > 40 ? 22 : 
                      this.text.length > 30 ? 26 : 28;
      return {
        fontSize: `${baseSize}px`,
        lineHeight: `${baseSize * 1.3}px`
      };
    },
    // 过滤器标签
    processedWords() {
      return (this.words || []).filter(word => {
      // 特别处理 insertion 类型
        if (word.errorType === 'insertion' && !this.errorFilters.insertion) return false;
        return true;
      });
    },
    // 弹窗位置
    popupStyle() {
      return {
        left: `${this.popupPosition.x}px`,
        top: `${this.popupPosition.y}px`,
        minWidth: `${this.popupWidth}px`,
        minHeight: `${this.popupHeight}px`,
        maxWidth: "650px" // 限制最大宽度，防止超出
      };
    }
  },
  data() {
    return {
      text: "",
      score: null, // 评估结果
      pron_score: null, // 发音评分
      accuracy: null, // 准确度
      fluency: null, // 流利度
      completeness: null, // 完整度
      prosody_score: null, // 韵律评分
      words: null, // 单词级评估
      errorMessage: "", // 错误信息
      isEvaluating: false, // 评估状态-禁用按钮
      isPlaying: false, // 录音播放状态
      recording: false, // 录音状态-禁用按钮
      mediaRecorder: null, // 录音对象
      audioChunks: [], // 存储音频数据
      audioBlob: null, // 存储音频 Blob
      audioUrl: null, // 存储录音播放 URL
      detailedResult: null, // 详细评估信息
      textareaHeight: 50, // 输入框初始高度
      errorFilters: {
        mispronunciation: true,
        omission: true,
        insertion: true,
        unexpectedBreak: true,
        missingBreak: true,
        monotone: true
      },
      expandedIndex: -1, // 展开的单词索引
      showTooltip: false,        // 控制显示/隐藏
      tooltipContent: '',        // 存储提示内容
      tooltipPosition: { x: 0, y: 0 }, // 存储提示位置
      controlButtons: [ // 按钮配置化
        {
          class: 'recording-button',
          action: this.toggleRecording,
          activeCondition: vm => vm.recording,
          text: vm => vm.recording ? "⏹ 停止录音 (R)" : "🎤 开始录音 (R)"
        },
        {
          class: 'play-button',
          action: this.playRecording,
          disabled: vm => !vm.audioBlob,
          text: vm => vm.isPlaying ? "🔊 播放中..." : "▶ 播放录音"
        },
        {
          class: 'evaluate-button',
          action: this.assessSpeech,
          disabled: vm => vm.isEvaluating || vm.recording, // 新增录音状态检查
          text: vm => vm.isEvaluating ? "正在评估..." : "开始语音评估"
        }
      ],
      showPopup: false, // 控制弹窗显示
      currentWordDetails: null, // 弹窗数据
      popupPosition: { x: 0, y: 0 }, // 存储弹窗位置
      popupWidth: 400, // 默认宽度
      popupHeight: 160 // 默认高度
    };
  },

  mounted() {
    document.addEventListener("keydown", this.handleKeydown);
    document.addEventListener("click", this.handleClickOutside);
  },

  beforeUnmount() {
    document.removeEventListener("click", this.handleClickOutside);
  },

  methods: {
    // 单词点击事件
    handleWordClick(word, index, event) {
      event.stopPropagation(); // 阻止冒泡，避免触发 handleClickOutside
      if (!word.Phonemes?.length) return; // 没有音素数据则不显示弹窗

      const rect = event.target.getBoundingClientRect(); // 获取单词位置

      // 设置弹窗数据
      this.currentWordDetails = {
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

      const popupWidth = this.popupWidth; // 获取默认弹窗宽度
      this.popupPosition = {
        x: rect.left + window.scrollX + rect.width / 2 - popupWidth / 2, // 水平方向居中
        y: rect.bottom + window.scrollY + 5 // 让弹窗在单词下方
      };
      this.showPopup = true;
    },

    handleClickOutside(event) {
      // 检查点击的元素是否是弹窗内部的元素
      if (this.$refs.popupEl && !this.$refs.popupEl.contains(event.target)) {
        this.showPopup = false;
      }
    },

    // 仿谷歌输入框自动调整高度
    autoResize() {
      this.$nextTick(() => {
        const textarea = this.$el.querySelector('.input-box');
        textarea.style.height = 'auto'; // 重置高度
        const newHeight = Math.min(textarea.scrollHeight + 5, 580); // 最大高度300px
        textarea.style.height = newHeight + 'px';
        this.textareaHeight = newHeight;
      });
    },

    // 添加过滤器标签翻译方法
    getFilterLabel(key) {
      const labels = {
        mispronunciation: '发音错误',
        omission: '单词缺失',
        insertion: '多余单词',
        unexpectedBreak: '意外停顿',
        missingBreak: '缺少停顿',
        monotone: '单调语音'
      };
      return labels[key] || key;
    },

    // 新增的errorType核心方法
    shouldHighlight(errorType) {
      return this.errorFilters[errorType] ? errorType : '';
    },

    // 新增展开/收起逻辑
    toggleExpand(index) {
      this.expandedIndex = this.expandedIndex === index ? -1 : index;
    },

    showPhonemesTooltip(word, event) {
      if (!word.Phonemes) return;
      
      // 1. 计算位置
      const rect = event.target.getBoundingClientRect();
      this.tooltipPosition = {
        x: rect.left + window.scrollX,  // 兼容页面滚动
        y: rect.top + window.scrollY - 40
      };
      
      // 2. 生成内容
      this.tooltipContent = word.Phonemes.map(p => `
        <div class="phoneme-row">
          <span>${p.Phoneme}</span>
          <span style="color: ${this.getPhonemeColor(p)}">
            ${p.PronunciationAssessment?.AccuracyScore ?? 'N/A'}
          </span>
        </div>
      `).join('');
      
      // 3. 显示提示
      this.showTooltip = true;
    },
    
    hideTooltip() {
      this.showTooltip = false;
      this.tooltipContent = '';
    },

    updateTooltipPosition(event) {
      if (!this.showTooltip) return;
      const rect = event.target.getBoundingClientRect();
      this.tooltipPosition = {
        x: rect.left + window.scrollX,
        y: rect.top + window.scrollY - 40
      };
    },

    getPhonemeColor(phoneme) {
      const score = phoneme.PronunciationAssessment?.AccuracyScore;
      if (score < 60) return '#dc2626';
      if (score < 80) return '#f4f4f5';
      return '#676769';
    },

    // 评分颜色
    getScoreClass(score) {
      const numericScore = Number(score);
      if (isNaN(numericScore)) return '';
      if (numericScore < 60) return 'score-low';
      if (numericScore <= 80) return 'score-mid';
      return 'score-high';
    },

    handleKeydown(event) {
      // 如果事件源是输入框或 textarea，则不触发快捷键逻辑
      const tagName = event.target.tagName.toLowerCase();
      if (tagName === "input" || tagName === "textarea") {
        return;
      }
      
      if (event.key === "r" && event.ctrlKey) {
        event.preventDefault(); // 阻止 Ctrl+R 导致浏览器刷新
        this.playRecording();
      } else if (event.key === "r" && !event.ctrlKey) {
        event.preventDefault();
        this.toggleRecording();
      }
    },

    // 录音相关功能
    async toggleRecording() {
      if (this.recording) {
        this.stopRecording();
      } else {
        await this.startRecording();
      }
    },

    async startRecording() {
      this.audioChunks = []; // 清空之前的录音
      this.audioBlob = null;
      this.audioUrl = null;

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.mediaRecorder = new MediaRecorder(stream);

        this.mediaRecorder.ondataavailable = (event) => {
          this.audioChunks.push(event.data);
        };

        this.mediaRecorder.onstop = () => {
          this.audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });
          this.audioUrl = URL.createObjectURL(this.audioBlob);
        };

        this.mediaRecorder.start();
        this.recording = true;
      } catch (error) {
        console.error("无法访问麦克风:", error);
        alert("无法访问麦克风，请检查权限设置。");
      }
    },

    stopRecording() {
      if (this.mediaRecorder && this.recording) {
        this.mediaRecorder.stop();
        this.recording = false;

        // 确保 Blob 以 WAV 格式存储
        this.audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });
        this.audioUrl = URL.createObjectURL(this.audioBlob);
      }
    },

    // 播放录音
    playRecording() {
      if (!this.audioUrl) {
        alert("没有可播放的录音");
        return;
      }

      if (this.isPlaying) return; // 防止重复播放

      this.isPlaying = true; // 播放开始，修改按钮状态
      const audio = new Audio(this.audioUrl);

      audio.onended = () => {
        this.isPlaying = false; // 播放结束，恢复按钮状态
      };

      audio.play();
    },

    // 语音评估
    async assessSpeech() {
      if (!this.text.trim()) {
        this.errorMessage = "请输入文本进行评估";
        return;
      }
      if (!this.audioBlob) {
        this.errorMessage = "请先录制语音文件";
        return;
      }

      this.isEvaluating = true; // 开始评估，禁用按钮
      this.errorMessage = ""; // 清除之前的错误信息

      const formData = new FormData();
      formData.append("audio", this.audioBlob, "recording.wav"); // 确保文件名为 .wav
      formData.append("reference_text", this.text);

      try {
        const res = await axios.post("http://127.0.0.1:5000/assessment/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });

        // 打印 detailedResult 数据结构
        console.log("detailedResult:", res.data.data.detailed_result);

        this.score = res.data.data.pronunciation_score; // 评估结果
        this.pron_score = res.data.data.pronunciation_score; // 发音评分
        this.accuracy = res.data.data.accuracy_score; // 准确度
        this.fluency = res.data.data.fluency_score; // 流利度
        this.completeness = res.data.data.completeness_score; // 完整度
        this.prosody_score = res.data.data.prosody_score; // 韵律评分
        this.detailedResult = res.data.data.detailed_result; // 详细评估信息
        const nBestData = this.detailedResult?.NBest?.[0] || {};
        // 处理单词数据
        this.words = nBestData.Words?.map(word => ({
           ...word,
           errorType: word.PronunciationAssessment?.ErrorType?.toLowerCase() || 'none'
         })) ?? [];

        // this.content_assessment_result = res.data.data.content_assessment_result; // 内容评估结果
        this.errorMessage = ""; // 清除错误信息
      } catch (error) {
        console.error("评估请求失败:", error);
        console.log("完整错误信息：", error);
        console.log("服务器返回数据：", error.response?.data);

        if (error.response && error.response.data) {
          this.errorMessage = error.response.data.message || "服务器返回未知错误";
        } else if (error.message) {
          this.errorMessage = error.message;
        } else {
          this.errorMessage = "无法连接语音评估服务器，请检查后端是否运行。";
        }

      } finally {
        this.isEvaluating = false; // 评估完成，恢复按钮
      }
    },


  }
};
</script>

<style scoped>
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

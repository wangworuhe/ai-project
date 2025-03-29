<template>
  <div class="assessment-container">
    <h2 class="title">语音评估</h2>

    <!-- 输入文本框 -->
    <!-- <textarea
      v-model="text"
      class="input-box"
      placeholder="输入文本进行评估..."
    ></textarea> -->

    <!-- 仿谷歌 输入文本框 -->
    <textarea v-model="text" @input="autoResize"
      :style="{ fontSize: dynamicFontSize + 'px', lineHeight: dynamicLineHeight }" class="input-box"
      placeholder="输入文本进行评估..."></textarea>

    <div class="button-group">
      <!-- 录音按钮 -->
      <button @click="toggleRecording" :class="recording ? 'recording-button active' : 'recording-button'">
        {{ recording ? "⏹ 停止录音 (R)" : "🎤 开始录音 (R)" }}
      </button>
      <!-- 播放录音按钮 -->
      <button @click="playRecording" :disabled="!audioBlob" :class="isPlaying ? 'play-button active' : 'play-button'">
        {{ isPlaying ? "🔊 播放中..." : "▶ 播放录音" }}
      </button>
      <!-- 评估发音按钮 -->
      <button @click="assessSpeech" :disabled="isEvaluating" class="evaluate-button">
        {{ isEvaluating ? "正在评估..." : "开始语音评估" }}
      </button>

    </div>

    <!-- 录音按钮 -->
    <!-- <button @click="toggleRecording" :class="recording ? 'recording-button active' : 'recording-button'">
      {{ recording ? "⏹ 停止录音 (R)" : "🎤 开始录音 (R)" }}
    </button> -->

    <!-- 播放录音按钮 -->
    <!-- <button @click="playRecording" :disabled="!audioBlob" :class="isPlaying ? 'play-button active' : 'play-button'">
      {{ isPlaying ? "🔊 播放中..." : "▶ 播放录音" }}
    </button> -->

    <!-- 评估发音按钮 -->
    <!-- <button @click="assessSpeech" :disabled="isEvaluating" class="evaluate-button">
      {{ isEvaluating ? "正在评估..." : "开始语音评估" }}
    </button> -->

    <!-- 显示错误信息 -->
    <br />
    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

    <!-- 评估结果 -->
    <div v-if="score !== null" class="result-container">
      <h3>评估结果</h3>
      <p>准确度: {{ accuracy }}%</p>
      <p>流利度: {{ fluency }}%</p>
      <p>完整度: {{ completeness }}%</p>
      <div v-if="detailedResult" class="detailed-result">
        <h3>详细评估信息</h3>
        <pre>{{ JSON.stringify(detailedResult, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";

export default {
  computed: {
    dynamicFontSize() {
      const baseSize = 26
      const charCount = this.text.length
      // 分段式缩放逻辑
      if (charCount > 40) return 20
      if (charCount > 30) return 24
      return baseSize
    },
    dynamicLineHeight() {
      return this.dynamicFontSize * 1.2 + 'px'
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
      content_assessment_result: null, // 内容评估结果
      errorMessage: "", // 错误信息
      isEvaluating: false, // 评估状态-禁用按钮
      isPlaying: false, // 录音播放状态
      recording: false, // 录音状态-禁用按钮
      mediaRecorder: null, // 录音对象
      audioChunks: [], // 存储音频数据
      audioBlob: null, // 存储音频 Blob
      audioUrl: null, // 存储录音播放 URL
      detailedResult: null, // 详细评估信息
      textareaHeight: 50 // 输入框初始高度
    };
  },

  mounted() {
    document.addEventListener("keydown", this.handleKeydown);
  },

  beforeUnmount() {
    document.removeEventListener("keydown", this.handleKeydown);
  },

  methods: {

    // 仿谷歌输入框自动调整高度
    autoResize() {
      this.$nextTick(() => {
        const textarea = this.$el.querySelector('.input-box')
        textarea.style.height = 'auto'  // 重置高度
        const newHeight = Math.min(textarea.scrollHeight + 5, 300) // 最大高度300px
        textarea.style.height = newHeight + 'px'
        this.textareaHeight = newHeight
      })
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
        // this.mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/wav" });

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

      this.isEvaluating = true; // 开始评估，禁用按钮

      const formData = new FormData();
      formData.append("audio", this.audioBlob, "recording.wav"); // 确保文件名为 .wav
      formData.append("reference_text", this.text);

      try {
        const res = await axios.post("http://127.0.0.1:5000/assessment/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });

        this.score = res.data.data.pronunciation_score; // 评估结果
        this.pron_score = res.data.data.pronunciation_score; // 发音评分
        this.accuracy = res.data.data.accuracy_score; // 准确度
        this.fluency = res.data.data.fluency_score; // 流利度
        this.completeness = res.data.data.completeness_score; // 完整度
        this.prosody_score = res.data.data.prosody_score; // 韵律评分
        this.detailedResult = res.data.data.detailed_result; // 详细评估信息
        this.words = res.data.data.words; // 单词级评估
        this.content_assessment_result = res.data.data.content_assessment_result; // 内容评估结果
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
    }
  }
};
</script>

<style scoped>
.title {
  font-size: 20px;       /* 字体大小 */
  font-weight: bold;     /* 字体加粗 */
  margin-top: 5px;
  margin-bottom: 10px;   /* 底部外边距 */
  text-align: center;    /* 文本居中 */
  width: 100%;           /* 确保宽度占满父容器 */
}

/* .assessment-container {
  max-width: 500px;
  margin: 0 auto;
  text-align: center;
} */

/* 修改后 */
.assessment-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 2px;
  display: flex;
  flex-direction: column;
  gap: 16px; /* 统一元素间距 */
}


/* 原始 */
/* .input-box {
  width: 100%;
  min-height: 50px;
  font-size: 16px;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 5px;
  resize: none;
} */

/* 仿谷歌样式 */
.input-box {
  width: 80%;
  margin: 0 auto;
  min-height: 70px; /* 最小高度保持 */
  letter-spacing: 0.2px;
  font-family: 'Google Sans', Arial, sans-serif;
  color: #1a0dab; /* Google文字蓝 */
  font-size: 16px;
  border-radius: 8px; /* 谷歌式圆角 */
  padding: 12px 20px; /* 与谷歌翻译相同的内边距 */
  box-shadow: 0 1px 6px rgba(32,33,36,.28); /* 谷歌Material Design阴影 */
  transition: all 0.3s cubic-bezier(0.4,0.0,0.2,1); /* 谷歌动画曲线 */
  border: 1px solid #dfe1e5; /* 谷歌翻译边框色 */
  resize: none; /* 禁止手动调整 */
  overflow-y: auto; /* 内容过多时显示滚动条 */
}

.input-box:focus {
  border-color: #4285f4; /* 谷歌蓝 */
  box-shadow: 0 1px 6px rgba(66,133,244,.28);
}

.button-group {
  margin-top: 16px; /* 与输入框保持间距 */
  display: flex;
  gap: 12px; /* 按钮间距 */
  justify-content: center;
  flex-wrap: wrap; /* 小屏幕换行 */
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
  margin-top: 15px;
  text-align: left;
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

.recording-button {
  padding: 10px 20px;
  background-color: #ff4d4d;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.3s;
}

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

</style>

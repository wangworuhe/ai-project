<template>
  <article class="mistake-book" role="tabpanel">
    <header class="mistake-header">
      <div>
        <p>错题本</p>
        <strong v-if="book">待复习 {{ book.summary.active }} · 已掌握 {{ book.summary.mastered }}</strong>
      </div>
      <div class="mistake-filters" aria-label="错题筛选">
        <button :class="{ active: scope === 'active' }" type="button" @click="setScope('active')">待复习</button>
        <button :class="{ active: scope === 'all' }" type="button" @click="setScope('all')">全部</button>
      </div>
    </header>

    <div v-if="loading" class="mistake-state">正在读取错题本…</div>
    <div v-else-if="error" class="mistake-state error" role="alert">{{ error }}</div>
    <div v-else-if="!book?.items.length" class="mistake-state">
      {{ scope === 'active' ? '目前没有待复习的错题。' : '错题本还是空的。' }}
    </div>
    <ol v-else class="mistake-list">
      <li v-for="item in book.items" :key="item.id" class="mistake-card">
        <div class="mistake-meta">
          <span>Unit {{ item.unit_number }}</span>
          <span>{{ item.exercise_number }} 第 {{ item.question_number }} 题</span>
          <span :class="`status-${item.status}`">{{ statusLabel(item) }}</span>
        </div>
        <p class="mistake-prompt">{{ questionText(item.question_content) }}</p>
        <dl>
          <div>
            <dt>你的错误答案</dt>
            <dd>{{ answerText(item.latest_wrong.user_answers) }}</dd>
          </div>
          <div>
            <dt>可接受答案</dt>
            <dd>
              <span v-for="(variant, index) in item.latest_wrong.accepted_variants" :key="index">
                {{ answerText(variant) }}<template v-if="index < item.latest_wrong.accepted_variants.length - 1">；</template>
              </span>
            </dd>
          </div>
        </dl>
        <footer>
          <span>累计答错 {{ item.wrong_count }} 次</span>
          <span v-if="item.correct_streak">连续答对 {{ item.correct_streak }} / {{ item.mastery_target }} 次</span>
          <button type="button" @click="$emit('review', item)">回到原题复习</button>
        </footer>
      </li>
    </ol>
  </article>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import api from '@/api'

const props = defineProps({ refreshKey: { type: Number, default: 0 } })
defineEmits(['review'])

const scope = ref('active')
const book = ref(null)
const loading = ref(false)
const error = ref('')
let requestNumber = 0

const load = async () => {
  const request = ++requestNumber
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/grammar/library/mistakes', {
      params: { status: scope.value }, timeout: 10000
    })
    if (request === requestNumber) book.value = data.data
  } catch (loadError) {
    if (request === requestNumber) {
      error.value = loadError.response?.data?.message || '无法读取错题本。'
    }
  } finally {
    if (request === requestNumber) loading.value = false
  }
}

const setScope = value => {
  if (scope.value === value) return
  scope.value = value
  load()
}

const answerText = values => Object.values(values || {})
  .filter(value => typeof value === 'string').join(' / ') || '—'
const questionText = content => {
  if (content?.prompt) {
    return content.cue ? `${content.prompt} (${content.cue})` : content.prompt
  }
  return (content?.segments || []).map(segment => (
    segment.type === 'input' ? '____' : segment.text || ''
  )).join('') || '题目内容不可用'
}
const statusLabel = item => ({
  reviewing: '待复习',
  improving: `巩固中 ${item.correct_streak}/${item.mastery_target}`,
  mastered: '已掌握'
})[item.status] || item.status

watch(() => props.refreshKey, load)
onMounted(load)
</script>

<style scoped>
.mistake-book { border: 1px solid #d7e0e3; background: #fff; box-shadow: 0 4px 14px rgba(24, 53, 93, .045); }
.mistake-header { display: flex; align-items: center; justify-content: space-between; gap: 18px; min-height: 58px; padding: 10px 16px; border-bottom: 1px solid #dbe3e7; background: #f5fafb; }
.mistake-header p { margin: 0 0 3px; color: #283885; font-size: .8rem; font-weight: 700; }
.mistake-header strong { color: #315c57; font-size: .84rem; }
.mistake-filters { display: flex; gap: 7px; }
.mistake-filters button,.mistake-card footer button { padding: 6px 10px; border: 1px solid #9bcfc9; background: #fff; color: #287268; cursor: pointer; }
.mistake-filters button.active { border-color: #283885; background: #283885; color: #fff; }
.mistake-state { padding: 50px 24px; color: #68757b; text-align: center; }
.mistake-state.error { color: #923f34; }
.mistake-list { display: grid; gap: 16px; margin: 0; padding: 24px clamp(18px, 4vw, 52px) 40px; list-style: none; }
.mistake-card { padding: 18px 20px; border: 1px solid #d9e2e4; border-left: 5px solid #bd5748; }
.mistake-meta { display: flex; flex-wrap: wrap; gap: 8px 15px; color: #68757b; font-size: .78rem; }
.mistake-meta span:first-child { color: #283885; font-weight: 700; }
.mistake-meta .status-improving { color: #9b701e; font-weight: 700; }
.mistake-meta .status-mastered { color: #257052; font-weight: 700; }
.mistake-meta .status-reviewing { color: #9a3d31; font-weight: 700; }
.mistake-prompt { margin: 14px 0; color: #20272b; font-size: 1.05rem; line-height: 1.55; }
.mistake-card dl { display: grid; gap: 8px; margin: 0; }
.mistake-card dl > div { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 10px; }
.mistake-card dt { color: #68757b; font-size: .8rem; }
.mistake-card dd { margin: 0; color: #244b9a; line-height: 1.45; }
.mistake-card footer { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; margin-top: 16px; padding-top: 12px; border-top: 1px solid #e6ebed; color: #68757b; font-size: .78rem; }
.mistake-card footer button { margin-left: auto; }
@media (max-width: 680px) { .mistake-header { align-items: flex-start; flex-direction: column; }.mistake-card dl > div { grid-template-columns: 1fr; gap: 3px; }.mistake-card footer button { width: 100%; margin-left: 0; } }
</style>

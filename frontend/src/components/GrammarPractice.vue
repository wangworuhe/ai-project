<template>
  <section class="book-reader">
    <header class="reader-header">
      <div>
        <h1>English Grammar in Use</h1>
        <p>第五版 · 已导入 {{ catalog?.units.length || 0 }} 个 Unit · 原书阅读与练习</p>
      </div>
      <p class="save-note">练习答案自动保存到数据库</p>
    </header>

    <div v-if="catalog && selectedUnit" class="reader-layout" :class="{ 'toc-is-collapsed': !isTocOpen }">
      <aside class="book-toc" aria-label="Unit 目录">
        <button
          class="toc-toggle"
          type="button"
          :aria-expanded="isTocOpen"
          :aria-label="isTocOpen ? '收起 Unit 目录' : '展开 Unit 目录'"
          :title="isTocOpen ? '收起目录' : '展开目录'"
          @click="isTocOpen = !isTocOpen"
        >
          <i></i><i></i><i></i>
        </button>
        <div v-show="isTocOpen" class="toc-list">
          <button
            v-for="unit in catalog.units"
            :key="unit.number"
            :class="{ selected: selectedUnit?.number === unit.number }"
            :aria-current="selectedUnit?.number === unit.number ? 'page' : undefined"
            :disabled="submitting"
            @click="selectUnit(unit.number)"
          >
            <span>Unit {{ unit.number }}</span>
            <strong>{{ unit.title }}</strong>
          </button>
        </div>
      </aside>

      <main v-if="selectedUnit" class="book-spread">
        <nav class="unit-tabs" role="tablist" aria-label="单元内容">
          <button
            type="button"
            role="tab"
            :class="{ active: activeSection === 'reading' }"
            :aria-selected="activeSection === 'reading'"
            :disabled="submitting"
            @click="selectSection('reading')"
          >正文</button>
          <button
            type="button"
            role="tab"
            :class="{ active: activeSection === 'exercise' }"
            :aria-selected="activeSection === 'exercise'"
            :disabled="submitting"
            @click="selectSection('exercise')"
          >练习</button>
          <button
            type="button"
            role="tab"
            :class="{ active: activeSection === 'mistakes' }"
            :aria-selected="activeSection === 'mistakes'"
            :disabled="submitting"
            @click="selectSection('mistakes')"
          >错题本</button>
        </nav>

        <div v-if="activeSection === 'mistakes'" class="spread-heading">
          <div>
            <p>Review</p>
            <h2>错题本</h2>
          </div>
          <span>根据正式提交记录自动更新</span>
        </div>
        <div v-else class="spread-heading">
          <div>
            <p>Unit {{ selectedUnit.number }}</p>
            <h2>{{ selectedUnit.title }}</h2>
          </div>
          <span>第 {{ selectedUnit.body_page - 12 }}–{{ selectedUnit.exercise_page - 12 }} 页</span>
        </div>

        <div class="pages" aria-live="polite">
          <GrammarMistakeBook
            v-if="activeSection === 'mistakes'"
            :refresh-key="mistakeRevision"
            @review="reviewMistake"
          />
          <div v-else-if="structuredLoading" class="book-state inline-state">正在读取结构化内容…</div>

          <template v-else-if="structuredUnit">
            <article v-if="activeSection === 'reading'" class="structured-page" role="tabpanel">
              <div class="structured-toolbar">
                <p>正文</p>
                <button type="button" @click="showOriginalPage = !showOriginalPage">
                  {{ showOriginalPage ? '收起原页' : '查看原页' }}
                </button>
              </div>

              <section
                v-for="section in structuredUnit.body"
                :key="section.label"
                class="lesson-section"
              >
                <div class="section-marker" aria-hidden="true">{{ section.label }}</div>
                <div class="section-content">
                  <p class="section-lead">{{ section.heading }}</p>
                  <div class="source-copy">
                    <p
                      v-for="(line, lineIndex) in section.lines"
                      :key="lineIndex"
                      class="source-line"
                      :class="{
                        'paragraph-start': line.paragraph_start && lineIndex > 0
                      }"
                    >
                      <span
                        v-for="(segment, segmentIndex) in line.segments"
                        :key="segmentIndex"
                        :class="{ strong: segment.bold, emphasis: segment.italic }"
                      >{{ segment.text }}</span>
                    </p>
                  </div>
                  <figure v-for="media in section.media" :key="media.id" class="lesson-media">
                    <img :src="media.url" :alt="media.alt">
                  </figure>
                </div>
              </section>

              <div v-if="showOriginalPage" class="original-reference">
                <p>原书正文页</p>
                <img :src="pageUrl(selectedUnit.body_page)" :alt="`Unit ${selectedUnit.number} 正文原书页`">
              </div>
            </article>

            <article v-else class="structured-page exercise-workbook" role="tabpanel">
              <div class="structured-toolbar exercise-status">
                <p>Exercises</p>
                <div>
                  <span>{{ answeredCount }} / {{ answerableCount }} 已填写</span>
                  <span v-if="draftError" class="draft-error" role="alert">{{ draftError }}</span>
                  <button
                    type="button"
                    class="submit-answers"
                    :disabled="submitting || !answerableCount || Boolean(submission)"
                    @click="submitAnswers"
                  >{{ submitting ? '正在判题…' : submission ? '已完成判题' : '提交并判题' }}</button>
                  <button type="button" @click="showOriginalPage = !showOriginalPage">
                    {{ showOriginalPage ? '收起原页' : '查看原页' }}
                  </button>
                </div>
              </div>

              <div v-if="submitError" class="submission-error" role="alert">
                {{ submitError }}
              </div>
              <div v-if="submission" class="submission-summary" aria-live="polite">
                <strong>
                  得分 {{ submission.summary.points_awarded }} / {{ submission.summary.points_possible }}
                </strong>
                <span>正确 {{ submission.summary.correct }}</span>
                <span>错误 {{ submission.summary.incorrect }}</span>
                <span v-if="submission.summary.incomplete">
                  未答完整 {{ submission.summary.incomplete }}
                </span>
                <span v-if="submission.summary.unanswered">
                  未作答 {{ submission.summary.unanswered }}
                </span>
                <span v-if="submission.summary.needs_review">
                  待审核 {{ submission.summary.needs_review }}
                </span>
                <small>提交记录 #{{ submission.id }}</small>
              </div>

              <section
                v-for="exercise in structuredUnit.exercises"
                :key="exercise.id"
                class="exercise-block"
              >
                <header class="exercise-heading">
                  <span>{{ exercise.number }}</span>
                  <h3>{{ exercise.instruction }}</h3>
                </header>

                <div v-if="exercise.word_bank.length" class="word-bank" aria-label="可选单词">
                  <span v-for="word in exercise.word_bank" :key="word">{{ word }}</span>
                </div>

                <figure v-for="media in exercise.media" :key="media.id" class="exercise-media">
                  <img :src="media.url" :alt="media.alt">
                </figure>

                <div v-if="exercise.type === 'matching'" class="matching-options">
                  <div v-for="option in exercise.options" :key="option.id">
                    <span>{{ option.id }}</span>
                    <p>{{ option.text }}</p>
                  </div>
                </div>

                <ol class="question-list">
                  <li
                    v-for="question in exercise.questions"
                    :key="question.id"
                    :value="Number(question.number)"
                    :data-question-id="question.id"
                    :class="[
                      { example: question.is_example },
                      { targeted: Number(route.query.question) === question.id },
                      resultFor(question.id)?.outcome
                        ? `result-${resultFor(question.id).outcome}`
                        : ''
                    ]"
                  >
                    <template v-if="question.is_example">
                      <p class="question-prompt">{{ question.content.prompt }}</p>
                      <span class="example-label">示例{{ rendererFor(exercise) === 'matching' ? `：${question.example_answer}` : '' }}</span>
                    </template>

                    <template v-else-if="rendererFor(exercise) === 'matching'">
                      <p class="question-prompt">{{ question.content.prompt }}</p>
                      <label class="visually-hidden" :for="`answer-${question.id}`">
                        第 {{ question.number }} 题答案
                      </label>
                      <select
                        :id="`answer-${question.id}`"
                        v-model="answers[answerKey(question)]"
                        class="matching-select"
                        data-answer-field
                        :disabled="submitting"
                        @change="handleImmediateAnswerChange"
                        @blur="flushDraftSave"
                        @mouseleave="flushDraftSave"
                      >
                        <option value="">选择</option>
                        <option v-for="option in exercise.options" :key="option.id" :value="option.id">
                          {{ option.id }}
                        </option>
                      </select>
                    </template>

                    <template v-else-if="rendererFor(exercise) === 'rewrite'">
                      <div class="rewrite-prompt">
                        <p class="question-prompt">{{ question.content.prompt }}</p>
                        <span v-if="question.content.cue">({{ question.content.cue }})</span>
                      </div>
                      <input
                        v-model="answers[answerKey(question)]"
                        class="text-answer full-answer"
                        data-answer-field
                        :aria-label="`第 ${question.number} 题答案`"
                        autocomplete="off"
                        spellcheck="false"
                        :disabled="submitting"
                        @input="scheduleDraftSave"
                        @blur="flushDraftSave"
                        @mouseleave="flushDraftSave"
                        @keydown.enter.prevent="focusAdjacentAnswer($event)"
                      >
                    </template>

                    <template v-else>
                      <div class="inline-question">
                        <template v-for="(segment, segmentIndex) in question.content.segments" :key="segmentIndex">
                          <span v-if="segment.type === 'text'">{{ segment.text }}</span>
                          <input
                            v-else-if="segment.type === 'input'"
                            v-model="answers[slotAnswerKey(question, segment.slot_key)]"
                            class="text-answer"
                            data-answer-field
                            :aria-label="answerLabel(question, segment.slot_key)"
                            autocomplete="off"
                            spellcheck="false"
                            :disabled="submitting"
                            @input="scheduleDraftSave"
                            @blur="flushDraftSave"
                            @mouseleave="flushDraftSave"
                            @keydown.enter.prevent="focusAdjacentAnswer($event)"
                          >
                          <span v-else-if="segment.type === 'cue'" class="answer-cue">({{ segment.text }})</span>
                        </template>
                        <span
                          v-if="question.content.cue && !question.content.segments?.some(segment => segment.type === 'cue')"
                          class="answer-cue"
                        >({{ question.content.cue }})</span>
                      </div>
                    </template>

                    <div
                      v-if="!question.is_example && resultFor(question.id)"
                      class="question-result"
                      :class="`result-${resultFor(question.id).outcome}`"
                      role="status"
                    >
                      <strong>{{ outcomeLabel(resultFor(question.id).outcome) }}</strong>
                      <div
                        v-if="resultFor(question.id).outcome !== 'correct' && resultFor(question.id).accepted_variants.length"
                        class="accepted-answers"
                      >
                        <span>可接受答案：</span>
                        <ul>
                          <li
                            v-for="(variant, variantIndex) in resultFor(question.id).accepted_variants"
                            :key="variantIndex"
                          >{{ formatAcceptedVariant(question, variant) }}</li>
                        </ul>
                      </div>
                    </div>
                  </li>
                </ol>
              </section>

              <div v-if="showOriginalPage" class="original-reference">
                <p>原书练习页</p>
                <img :src="pageUrl(selectedUnit.exercise_page)" :alt="`Unit ${selectedUnit.number} 练习原书页`">
              </div>
            </article>
          </template>

          <div v-else class="book-state inline-state error-state">
            该 Unit 的结构化内容暂时不可用。
          </div>
        </div>
      </main>
    </div>

    <div v-else-if="loadError" class="book-state error-state">{{ loadError }}</div>
    <div v-else-if="catalog" class="book-state">尚无已发布的结构化单元。</div>
    <div v-else class="book-state">正在读取书籍目录…</div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import GrammarMistakeBook from '@/components/GrammarMistakeBook.vue'

const route = useRoute()
const router = useRouter()
const catalog = ref(null)
const structuredUnit = ref(null)
const structuredLoading = ref(false)
const answers = ref({})
const draftError = ref('')
const submission = ref(null)
const submitting = ref(false)
const submitError = ref('')
const loadError = ref('')
const isTocOpen = ref(true)
const showOriginalPage = ref(false)
const mistakeRevision = ref(0)
let structuredRequest = 0
let draftSaveTimer = null
let draftSaveQueue = Promise.resolve()
const lastPersistedDraft = new Map()
const queuedDraft = new Map()
const DRAFT_SAVE_DELAY = 2000

const EXERCISE_RENDERERS = Object.freeze({
  fill: 'inline',
  matching: 'matching',
  'picture-fill': 'inline',
  rewrite: 'rewrite'
})

const selectedUnit = computed(() => {
  if (!catalog.value?.units.length) return null
  const requested = Number(route.query.unit)
  return catalog.value.units.find(unit => unit.number === requested) || catalog.value.units[0]
})

const activeSection = computed(() => (
  ['exercise', 'mistakes'].includes(route.query.section) ? route.query.section : 'reading'
))
const answerableSlots = computed(() => (
  structuredUnit.value?.exercises.flatMap(exercise => (
    exercise.questions.flatMap(question => (
      question.is_example ? [] : question.slots
    ))
  )) || []
))
const answerableCount = computed(() => answerableSlots.value.length)
const answeredCount = computed(() => answerableSlots.value.filter(slot => {
  const value = answers.value[slot.answer_key]
  return typeof value === 'string' && value.trim().length > 0
}).length)
const resultsByQuestion = computed(() => new Map(
  (submission.value?.results || []).map(result => [result.question_id, result])
))

const pageUrl = pageNumber => `/api/grammar/book-pages/${pageNumber}`
const rendererFor = exercise => EXERCISE_RENDERERS[exercise.type] || 'unsupported'
const slotAnswerKey = (question, slotKey) => {
  const slot = question.slots.find(item => item.key === slotKey) || question.slots[0]
  return slot?.answer_key || `question-${question.id}-${slotKey || 'answer-1'}`
}
const answerKey = question => slotAnswerKey(question, question.slots[0]?.key)
const answerLabel = (question, slotKey) => {
  const slotIndex = question.slots.findIndex(item => item.key === slotKey)
  return question.slots.length > 1
    ? `第 ${question.number} 题第 ${slotIndex + 1} 个答案`
    : `第 ${question.number} 题答案`
}
const resultFor = questionId => resultsByQuestion.value.get(questionId)
const outcomeLabel = outcome => ({
  correct: '正确',
  incorrect: '错误',
  incomplete: '未答完整',
  unanswered: '未作答',
  needs_review: '当前答案规则无法安全判定，需进一步审核'
})[outcome] || '待审核'
const formatAcceptedVariant = (question, variant) => question.slots
  .map(slot => variant[slot.key])
  .filter(value => typeof value === 'string')
  .join(' / ')

const invalidateSubmission = () => {
  submission.value = null
  submitError.value = ''
}

const draftKeyFor = unit => (
  `${catalog.value.book.edition}-unit-${unit.number}-page-${unit.exercise_page}`
)

const readLocalDraft = key => {
  try {
    return JSON.parse(localStorage.getItem(key) || '{}')
  } catch {
    return {}
  }
}

const writeLocalDraft = (key, values) => {
  const nonEmptyAnswers = Object.fromEntries(
    Object.entries(values).filter(([, value]) => (
      typeof value === 'string' && value.trim().length > 0
    ))
  )
  try {
    if (Object.keys(nonEmptyAnswers).length) {
      localStorage.setItem(key, JSON.stringify(nonEmptyAnswers))
    } else {
      localStorage.removeItem(key)
    }
  } catch {
    // Database persistence remains available when browser storage is disabled.
  }
  return nonEmptyAnswers
}

const buildDraftContext = (unit, values) => {
  if (!unit || !catalog.value?.book) return null
  const rows = unit.exercises.flatMap(exercise => (
    exercise.questions.flatMap(question => (
      question.is_example
        ? []
        : question.slots.map(slot => ({
            slot_id: slot.id,
            value: typeof values[slot.answer_key] === 'string' ? values[slot.answer_key] : ''
          }))
    ))
  ))
  return {
    unitNumber: unit.number,
    localKey: draftKeyFor(unit),
    localValues: { ...values },
    answers: rows,
    questionVersions: unit.exercises.flatMap(exercise => (
      exercise.questions
        .filter(question => !question.is_example)
        .map(question => ({
          question_id: question.id,
          version: question.submission_version
        }))
    )),
    fingerprint: JSON.stringify(rows)
  }
}

const saveFailureMessage = error => {
  const reason = error.response?.data?.message
  if (reason) return `答案保存失败：${reason}`
  if (!error.response) return '答案保存失败：无法连接服务器，答案仍保留在本机。'
  return `答案保存失败：服务器返回 ${error.response.status}。`
}

const queueDraftSave = context => {
  if (!context) return draftSaveQueue
  const cachedValues = writeLocalDraft(context.localKey, context.localValues)
  const pendingFingerprint = queuedDraft.get(context.unitNumber)
  if (pendingFingerprint === context.fingerprint) return draftSaveQueue
  if (
    pendingFingerprint === undefined &&
    lastPersistedDraft.get(context.unitNumber) === context.fingerprint
  ) return draftSaveQueue

  queuedDraft.set(context.unitNumber, context.fingerprint)
  draftSaveQueue = draftSaveQueue.then(async () => {
    try {
      await api.put(`/grammar/library/units/${context.unitNumber}/draft`, {
        answers: context.answers
      }, { timeout: 10000 })
      lastPersistedDraft.set(context.unitNumber, context.fingerprint)
      if (JSON.stringify(readLocalDraft(context.localKey)) === JSON.stringify(cachedValues)) {
        try {
          localStorage.removeItem(context.localKey)
        } catch {
          // The server save succeeded; a browser-cache cleanup failure is harmless.
        }
      }
      if (structuredUnit.value?.number === context.unitNumber) draftError.value = ''
    } catch (error) {
      if (structuredUnit.value?.number === context.unitNumber) {
        draftError.value = saveFailureMessage(error)
      }
    } finally {
      if (queuedDraft.get(context.unitNumber) === context.fingerprint) {
        queuedDraft.delete(context.unitNumber)
      }
    }
  })
  return draftSaveQueue
}

const scheduleDraftSave = () => {
  invalidateSubmission()
  const context = buildDraftContext(structuredUnit.value, { ...answers.value })
  if (!context) return
  writeLocalDraft(context.localKey, answers.value)
  window.clearTimeout(draftSaveTimer)
  draftSaveTimer = window.setTimeout(() => queueDraftSave(context), DRAFT_SAVE_DELAY)
}

const handleImmediateAnswerChange = () => {
  invalidateSubmission()
  flushDraftSave()
}

const flushDraftSave = () => {
  window.clearTimeout(draftSaveTimer)
  draftSaveTimer = null
  return queueDraftSave(buildDraftContext(structuredUnit.value, { ...answers.value }))
}

const loadStructuredUnit = async number => {
  const request = ++structuredRequest
  structuredUnit.value = null
  structuredLoading.value = true
  loadError.value = ''
  draftError.value = ''
  submission.value = null
  submitError.value = ''
  try {
    const { data } = await api.get(`/grammar/library/units/${number}`)
    if (request !== structuredRequest) return
    const unit = data.data
    const localKey = draftKeyFor(unit)
    const localAnswers = readLocalDraft(localKey)
    let serverAnswers = {}
    try {
      const draftResponse = await api.get(
        `/grammar/library/units/${number}/draft`, { timeout: 10000 }
      )
      const answerKeyBySlotId = new Map(
        unit.exercises.flatMap(exercise => exercise.questions).flatMap(question => question.slots)
          .map(slot => [slot.id, slot.answer_key])
      )
      serverAnswers = Object.fromEntries(
        draftResponse.data.data.answers
          .filter(item => answerKeyBySlotId.has(item.slot_id))
          .map(item => [answerKeyBySlotId.get(item.slot_id), item.value])
      )
    } catch (error) {
      draftError.value = saveFailureMessage(error).replace('保存失败', '读取失败')
    }
    if (request !== structuredRequest) return
    structuredUnit.value = unit
    const serverContext = buildDraftContext(unit, serverAnswers)
    lastPersistedDraft.set(number, serverContext.fingerprint)
    answers.value = { ...serverAnswers, ...localAnswers }
    const mergedContext = buildDraftContext(unit, answers.value)
    if (mergedContext.fingerprint !== serverContext.fingerprint) {
      queueDraftSave(mergedContext)
    }
    const targetQuestion = Number(route.query.question)
    if (Number.isInteger(targetQuestion) && targetQuestion > 0) {
      await nextTick()
      document.querySelector(`[data-question-id="${targetQuestion}"]`)?.scrollIntoView({
        behavior: 'smooth', block: 'center'
      })
    }
  } catch (error) {
    if (request === structuredRequest) {
      loadError.value = error.response?.data?.message || '无法读取结构化书籍内容。'
    }
  } finally {
    if (request === structuredRequest) structuredLoading.value = false
  }
}

const submitAnswers = async () => {
  const context = buildDraftContext(structuredUnit.value, { ...answers.value })
  if (!context || submitting.value) return
  submitting.value = true
  submitError.value = ''
  try {
    await flushDraftSave()
    const { data } = await api.post(
      `/grammar/library/units/${context.unitNumber}/submissions`,
      {
        answers: context.answers,
        question_versions: context.questionVersions
      },
      { timeout: 30000 }
    )
    const currentContext = buildDraftContext(structuredUnit.value, { ...answers.value })
    if (
      currentContext?.unitNumber !== context.unitNumber ||
      currentContext?.fingerprint !== context.fingerprint
    ) {
      submitError.value = '答案在提交期间发生变化，请重新提交。'
      return
    }
    submission.value = data.data
    mistakeRevision.value += 1
  } catch (error) {
    submitError.value = error.response?.data?.message || '提交判题失败，请稍后重试。'
  } finally {
    submitting.value = false
  }
}

const selectUnit = number => {
  if (submitting.value) return
  flushDraftSave()
  const query = { unit: String(number) }
  if (activeSection.value !== 'reading') query.section = activeSection.value
  router.replace({ query })
}

const selectSection = section => {
  if (submitting.value) return
  if (activeSection.value === 'exercise') flushDraftSave()
  const query = { unit: String(selectedUnit.value.number) }
  if (section !== 'reading') query.section = section
  router.replace({ query })
}

const reviewMistake = async item => {
  if (submitting.value) return
  await router.replace({
    query: {
      unit: String(item.unit_number),
      section: 'exercise',
      question: String(item.question_id)
    }
  })
  if (structuredUnit.value?.number === item.unit_number) {
    await nextTick()
    document.querySelector(`[data-question-id="${item.question_id}"]`)?.scrollIntoView({
      behavior: 'smooth', block: 'center'
    })
  }
}

const focusAdjacentAnswer = async event => {
  await nextTick()
  const fields = [...document.querySelectorAll('.exercise-workbook [data-answer-field]')]
  const current = fields.indexOf(event.currentTarget)
  const offset = event.shiftKey ? -1 : 1
  fields[current + offset]?.focus()
}

watch(selectedUnit, unit => {
  if (!unit) return
  showOriginalPage.value = false
  loadStructuredUnit(unit.number)
})

watch(activeSection, () => {
  showOriginalPage.value = false
})

onMounted(async () => {
  try {
    const { data } = await api.get('/grammar/library/units')
    catalog.value = data.data
    if (catalog.value.units.length && (
      !route.query.unit ||
      !catalog.value.units.some(unit => unit.number === Number(route.query.unit))
    )) {
      await router.replace({ query: { unit: String(catalog.value.units[0].number) } })
    }
  } catch (error) {
    loadError.value = error.response?.data?.message || '无法读取数据库书籍目录。'
  }
})

onBeforeUnmount(() => {
  flushDraftSave()
})
</script>

<style scoped>
.book-reader { --book-blue: #283885; --book-cyan: #d9f0f4; --book-mint: #58c7b7; --book-ink: #20272b; --book-muted: #68757b; --book-line: #d3dde1; --book-paper: #fff; max-width: 1620px; margin: 0 auto; padding: 26px clamp(16px, 3vw, 48px) 64px; color: var(--book-ink); font-family: Arial, Helvetica, "PingFang SC", sans-serif; }
.reader-header { display: flex; justify-content: space-between; gap: 24px; align-items: end; padding: 0 0 18px; border-bottom: 4px solid var(--book-blue); }
.reader-header h1,.reader-header p { margin: 0; }
.reader-header h1 { color: var(--book-blue); font: 700 clamp(1.55rem, 3.4vw, 2.65rem)/1.08 Arial, Helvetica, sans-serif; letter-spacing: -.035em; }
.reader-header > div p { margin-top: 7px; color: var(--book-muted); font-size: .9rem; }
.save-note { padding: 7px 10px; border: 1px solid #96d7cf; color: #2c756c; font-size: .78rem; white-space: nowrap; }
.reader-layout { display: grid; grid-template-columns: 244px minmax(0, 1fr); gap: clamp(20px, 3vw, 48px); padding-top: 27px; }
.reader-layout.toc-is-collapsed { position: relative; display: block; }
.reader-layout.toc-is-collapsed .book-toc { position: absolute; top: 27px; left: 0; z-index: 2; }
.reader-layout.toc-is-collapsed .book-spread { width: min(100%, 1080px); margin-inline: auto; }
.book-toc { position: sticky; top: 16px; align-self: start; border-top: 1px solid var(--book-line); }
.toc-toggle { display: grid; place-content: center; gap: 4px; width: 48px; height: 42px; margin: 8px 0; padding: 0; border: 1px solid #bcd6d9; background: #f7fbfc; cursor: pointer; }
.toc-toggle:hover { background: var(--book-cyan); }
.toc-toggle:focus-visible,.unit-tabs button:focus-visible,.structured-toolbar button:focus-visible { outline: 3px solid #e59441; outline-offset: 2px; }
.toc-toggle i { display: block; width: 18px; height: 2px; background: var(--book-blue); }
.toc-list button { width: 100%; display: grid; gap: 5px; padding: 13px 12px 14px; border: 0; border-left: 5px solid transparent; border-bottom: 1px solid #e1e6e9; background: transparent; color: var(--book-ink); text-align: left; cursor: pointer; }
.toc-list button:hover { background: #edf8f7; }
.toc-list button.selected { border-left-color: var(--book-mint); background: var(--book-cyan); }
.toc-list span { color: #617077; font-size: .75rem; }
.toc-list strong { font-size: .9rem; font-weight: 650; line-height: 1.32; }
.book-spread,.pages { min-width: 0; }
.unit-tabs { display: flex; width: min(100%, 1080px); margin-bottom: 19px; border-bottom: 1px solid var(--book-line); }
.unit-tabs button { min-width: 92px; padding: 10px 24px 9px; border: 0; border-bottom: 3px solid transparent; background: transparent; color: #66757c; font-size: .92rem; font-weight: 650; cursor: pointer; }
.unit-tabs button:hover { color: var(--book-blue); background: #f2f8f8; }
.unit-tabs button.active { border-bottom-color: var(--book-mint); color: var(--book-blue); }
.spread-heading { display: flex; align-items: end; justify-content: space-between; gap: 20px; padding: 0 0 16px; }
.spread-heading p,.spread-heading h2 { margin: 0; }
.spread-heading p { color: var(--book-mint); font-weight: 700; font-size: .82rem; }
.spread-heading h2 { margin-top: 3px; color: var(--book-blue); font: 700 clamp(1.35rem, 2.5vw, 2.1rem)/1.15 Arial, Helvetica, sans-serif; letter-spacing: -.025em; }
.spread-heading > span { color: var(--book-muted); font-size: .78rem; white-space: nowrap; }
.pages { width: min(100%, 1080px); }
.structured-page { border: 1px solid #d7e0e3; background: var(--book-paper); box-shadow: 0 4px 14px rgba(24, 53, 93, .045); }
.structured-toolbar { display: flex; justify-content: space-between; align-items: center; min-height: 42px; padding: 0 14px; border-bottom: 1px solid #dbe3e7; background: #f5fafb; }
.structured-toolbar p { margin: 0; color: var(--book-blue); font-size: .78rem; font-weight: 700; }
.structured-toolbar button { padding: 5px 9px; border: 1px solid #9bcfc9; background: #fff; color: #287268; cursor: pointer; }
.lesson-section { display: grid; grid-template-columns: 48px minmax(0, 1fr); margin: 0 clamp(24px, 4vw, 52px); padding: 34px 0 38px; border-bottom: 1px solid var(--book-line); }
.lesson-section:last-of-type { border-bottom: 0; }
.section-marker { align-self: start; margin-top: 1px; padding: 6px 0 5px; background: var(--book-mint); color: #fff; text-align: center; font: 700 1rem/1 Arial, sans-serif; }
.section-content { min-width: 0; padding-left: clamp(22px, 3.5vw, 42px); }
.source-copy { max-width: 72ch; color: #20282c; font: 400 clamp(1.02rem, .25vw + .96rem, 1.09rem)/1.64 Arial, Helvetica, "PingFang SC", sans-serif; }
.source-line { min-height: 1.25em; margin: 0; }
.section-lead { max-width: 72ch; margin: 0 0 17px; color: #20272a; font-size: 1.07rem; font-weight: 600; line-height: 1.5; }
.source-line.paragraph-start { margin-top: 18px; }
.source-line .strong { font-weight: 700; }
.source-line .emphasis { font-style: italic; }
.lesson-media { margin: 24px 0 2px; }
.lesson-media img { display: block; max-width: min(100%, 580px); height: auto; }
.exercise-status > div { display: flex; align-items: center; gap: 14px; color: #3e756e; font-size: .75rem; }
.draft-error { max-width: 520px; color: #a23f34; font-weight: 650; }
.structured-toolbar .submit-answers { border-color: var(--book-blue); background: var(--book-blue); color: #fff; font-weight: 700; }
.structured-toolbar .submit-answers:disabled { cursor: wait; opacity: .58; }
.submission-error { margin: 16px clamp(24px, 5vw, 64px) 0; padding: 11px 14px; border-left: 4px solid #b34a3c; background: #fff3f0; color: #8c332a; }
.submission-summary { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: baseline; margin: 20px clamp(24px, 5vw, 64px) 0; padding: 14px 16px; border: 1px solid #a8d8d1; background: #f2faf8; color: #315c57; }
.submission-summary strong { color: var(--book-blue); font-size: 1.05rem; }
.submission-summary small { margin-left: auto; color: var(--book-muted); }
.exercise-workbook { font-size: 1.04rem; }
.exercise-block { padding: 36px clamp(24px, 5vw, 64px) 42px; border-bottom: 1px solid #cad8dd; }
.exercise-block:last-of-type { border-bottom: 0; }
.exercise-heading { display: grid; grid-template-columns: 58px minmax(0, 1fr); gap: 16px; align-items: start; }
.exercise-heading > span { padding: 8px 4px 7px; background: var(--book-mint); color: #fff; text-align: center; font-weight: 700; }
.exercise-heading h3 { margin: 3px 0 0; font: 700 1.08rem/1.45 Arial, Helvetica, sans-serif; }
.word-bank { display: flex; flex-wrap: wrap; gap: 8px 22px; width: fit-content; max-width: calc(100% - 70px); margin: 16px 0 20px 70px; padding: 8px 14px; border: 1px solid #ebcf6d; border-radius: 16px; font-weight: 650; }
.exercise-media { margin: 18px 0 22px 70px; overflow-x: auto; }
.exercise-media img { display: block; width: min(100%, 630px); min-width: 520px; height: auto; }
.matching-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px 36px; max-width: 800px; margin: 24px 0 28px 74px; padding: 18px 22px; border-left: 3px solid var(--book-mint); background: #f2f9f8; font-size: 1.08rem; line-height: 1.45; }
.matching-options > div { display: grid; grid-template-columns: 24px 1fr; gap: 7px; }
.matching-options span { color: #3cb6a6; font-weight: 700; }
.matching-options p { margin: 0; }
.question-list { display: grid; gap: 13px; margin: 25px 0 0 74px; padding-left: 30px; }
.question-list > li { padding: 5px 8px; font-size: 1.06rem; line-height: 1.62; }
.question-list > li::marker { color: #4abfae; font-weight: 700; }
.question-list > li:focus-within { box-shadow: inset 3px 0 0 rgba(88, 199, 183, .65); }
.question-list > li.targeted { outline: 3px solid rgba(229, 148, 65, .75); outline-offset: 5px; }
.question-list > li.result-correct { background: #f2faf6; }
.question-list > li.result-incorrect,.question-list > li.result-incomplete { background: #fff5f2; }
.question-list > li.result-unanswered,.question-list > li.result-needs_review { background: #fff9e9; }
.question-result { margin-top: 8px; padding: 8px 11px; border-left: 3px solid #d4a642; font-size: .88rem; line-height: 1.45; }
.question-result.result-correct { border-left-color: #3d9b75; color: #257052; }
.question-result.result-incorrect,.question-result.result-incomplete { border-left-color: #bd5748; color: #8d352c; }
.question-result.result-unanswered,.question-result.result-needs_review { color: #79601f; }
.accepted-answers { margin-top: 5px; color: #4b5559; }
.accepted-answers ul { margin: 3px 0 0; padding-left: 20px; }
.question-list > li.example { color: #536168; }
.question-prompt { margin: 0; }
.example-label { display: inline-block; margin-top: 4px; color: #347b72; font-size: .75rem; }
.matching-select { width: 68px; margin-top: 4px; padding: 3px 22px 3px 5px; border: 0; border-bottom: 1.5px solid #79b9b0; border-radius: 0; outline: 0; appearance: none; background-color: transparent; background-image: linear-gradient(45deg, transparent 50%, #4d7773 50%), linear-gradient(135deg, #4d7773 50%, transparent 50%); background-position: calc(100% - 10px) 55%, calc(100% - 6px) 55%; background-size: 4px 4px, 4px 4px; background-repeat: no-repeat; color: #244b9a; font: 600 1.02rem/1.35 Arial, sans-serif; cursor: pointer; }
.matching-select:focus-visible { border-bottom-color: var(--book-blue); box-shadow: 0 2px 0 rgba(40, 56, 133, .18); }
.rewrite-prompt { display: flex; justify-content: space-between; gap: 20px; align-items: baseline; }
.inline-question .answer-cue { margin: 0 3px; }
.inline-question { max-width: 85ch; }
.text-answer { min-width: min(270px, 70vw); margin: 0 5px; padding: 3px 4px 2px; border: 0; border-bottom: 1.5px solid #79b9b0; border-radius: 0; outline: 0; background: transparent; color: #244b9a; caret-color: var(--book-blue); font: 600 1.04rem/1.35 Arial, Helvetica, sans-serif; }
.text-answer:hover { border-bottom-color: #479f94; }
.text-answer:focus { border-bottom-color: var(--book-blue); box-shadow: 0 2px 0 rgba(40, 56, 133, .18); }
.full-answer { display: block; width: min(100%, 780px); margin: 9px 0 0; }
.original-reference { margin: 24px; padding-top: 18px; border-top: 1px solid var(--book-line); }
.original-reference p { color: var(--book-blue); font-size: .78rem; font-weight: 700; }
.original-reference img { display: block; width: 100%; height: auto; }
.book-state { margin: 70px auto; max-width: 600px; padding: 28px; border: 1px solid var(--book-line); text-align: center; color: #5e6c73; }
.inline-state { margin: 0; max-width: none; }
.error-state { border-color: #d59b92; color: #923f34; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 980px) { .reader-layout,.reader-layout.toc-is-collapsed { display: grid; grid-template-columns: 1fr; gap: 18px; }.reader-layout.toc-is-collapsed .book-toc { position: static; }.reader-layout.toc-is-collapsed .book-spread { width: 100%; }.book-toc { position: static; display: flex; gap: 10px; align-items: start; border-bottom: 1px solid var(--book-line); }.toc-toggle { flex: 0 0 48px; }.toc-list { display: flex; flex: 1; overflow-x: auto; }.toc-list button { min-width: 180px; border-left: 0; border-bottom: 4px solid transparent; }.toc-list button.selected { border-left: 0; border-bottom-color: var(--book-mint); } }
@media (max-width: 680px) { .book-reader { padding: 18px 10px 36px; }.reader-header { align-items: start; flex-direction: column; }.save-note { white-space: normal; }.spread-heading { align-items: start; flex-direction: column; gap: 6px; }.lesson-section { grid-template-columns: 38px minmax(0, 1fr); margin: 0 12px; }.section-content { padding-left: 12px; }.exercise-block { padding-inline: 14px; }.exercise-heading { grid-template-columns: 48px minmax(0, 1fr); }.word-bank,.exercise-media,.matching-options,.question-list { margin-left: 0; }.matching-options { grid-template-columns: 1fr; }.exercise-status { align-items: start; gap: 8px; }.exercise-status > div { flex-wrap: wrap; justify-content: flex-end; gap: 6px 10px; }.rewrite-prompt { align-items: start; flex-direction: column; gap: 2px; }.text-answer { width: calc(100% - 10px); min-width: 0; } }
</style>

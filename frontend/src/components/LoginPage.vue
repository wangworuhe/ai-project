<template>
  <div class="login-page">
    <section class="login-intro" aria-label="英语学习空间">
      <span class="book-mark" aria-hidden="true">Aa</span>
      <h1>每天，<br>学会多一点。</h1>
      <p>语法练习、发音与表达。<br>从上次停下的地方继续。</p>
    </section>
    <section class="login-panel">
      <form class="login-form" @submit.prevent="submit">
        <h2>登录学习空间</h2>
        <p class="welcome">欢迎回来，开始今天的练习。</p>
        <label for="username">账号</label>
        <input id="username" v-model="username" name="username" autocomplete="username" required maxlength="128">
        <label for="password">密码</label>
        <input id="password" v-model="password" name="password" type="password" autocomplete="current-password" required maxlength="1024">
        <p class="session-note">登录后保持 60 天，退出登录可提前结束。</p>
        <p v-if="error" class="login-error" role="alert">{{ error }}</p>
        <button type="submit" :disabled="busy">{{ busy ? '正在登录…' : '登录' }}</button>
      </form>
    </section>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { login } from '../auth'
const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
const router = useRouter()
const route = useRoute()
async function submit() {
  busy.value = true
  error.value = ''
  try {
    await login(username.value, password.value)
    password.value = ''
    const next = route.query.next
    await router.replace(typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login') ? next : '/grammar')
  } catch (failure) {
    error.value = failure.response?.data?.message || '无法连接，请检查网络后重试。'
  } finally {
    busy.value = false
  }
}
</script>
<style scoped>
.login-page { min-height: 100vh; display: grid; grid-template-columns: 1fr 1fr; background: #f8fafc; color: #19394a; font-family: "PingFang SC", "Microsoft YaHei", sans-serif; }
.login-intro { background: #dcecef; padding: clamp(40px, 8vw, 120px); display: flex; flex-direction: column; justify-content: center; }
.book-mark { font: 48px Georgia, serif; border-bottom: 3px solid #276474; width: fit-content; padding-bottom: 8px; }
h1 { font-size: clamp(36px, 4vw, 60px); font-weight: 600; line-height: 1.4; margin: 32px 0 20px; letter-spacing: 2px; }
.login-intro p { font-size: 17px; line-height: 1.9; color: #446271; }
.login-panel { display: flex; align-items: center; justify-content: center; padding: 48px 28px; }
.login-form { width: 100%; max-width: 350px; }
h2 { margin: 0 0 12px; font-size: 28px; font-weight: 600; }
.welcome { color: #657583; margin-bottom: 36px; line-height: 1.7; }
label { display: block; font-size: 15px; margin: 22px 0 9px; }
input { box-sizing: border-box; width: 100%; border: 1px solid #a5b9c2; border-radius: 6px; padding: 13px; font: inherit; background: white; color: #19394a; }
input:focus-visible, button:focus-visible { outline: 3px solid #5196ab; outline-offset: 3px; }
.session-note { color: #657583; font-size: 13px; line-height: 1.7; margin: 18px 0 26px; }
button { width: 100%; border: 0; border-radius: 6px; padding: 14px; background: #276474; color: white; font: inherit; cursor: pointer; }
button:hover { background: #1c5160; } button:disabled { opacity: .65; cursor: wait; }
.login-error { color: #a32626; font-size: 14px; line-height: 1.6; }
@media (max-width: 680px) { .login-page { grid-template-columns: 1fr; } .login-intro { padding: 26px 28px; } .book-mark { font-size: 30px; } h1 { font-size: 28px; margin: 18px 0 0; } h1 br { display: none; } .login-intro p { display: none; } .login-panel { align-items: flex-start; padding-top: 36px; } }
</style>

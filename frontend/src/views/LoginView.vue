<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { useNavigationStore } from '@/stores/navigation'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import { register as apiRegister } from '@/services/auth'

const auth = useAuthStore()
const nav = useNavigationStore()

const serverUrl = ref(localStorage.getItem('vguard_server') || '')
const loginUser = ref('')
const loginPass = ref('')
const loginError = ref('')
const loading = ref(false)
const mode = ref<'login' | 'register'>('login')
const registerHint = ref('')

function setServer() {
  const v = serverUrl.value.trim().replace(/\/+$/, '')
  localStorage.setItem('vguard_server', v)
  serverUrl.value = v
}

async function registerUser() {
  registerHint.value = ''
  loginError.value = ''
  loading.value = true
  try {
    await apiRegister(loginUser.value, loginPass.value)
    registerHint.value = '注册成功，请直接登录'
    mode.value = 'login'
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      loginError.value = '用户名已存在'
    } else if (axios.isAxiosError(error) && error.response?.status === 400) {
      loginError.value = '用户名或密码太短'
    } else {
      loginError.value = '注册失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}

async function submit() {
  loginError.value = ''
  loading.value = true
  try {
    await auth.login(loginUser.value, loginPass.value)
    nav.push('home')
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && !error.response) {
      loginError.value = '无法连接后端服务，请先启动后端或检查端口映射'
    } else if (axios.isAxiosError(error) && error.response?.status === 401) {
      loginError.value = '用户名或密码错误'
    } else {
      loginError.value = '登录失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen relative overflow-hidden">
    <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.16),transparent_30%),radial-gradient(circle_at_bottom_left,rgba(14,165,233,0.10),transparent_26%),linear-gradient(180deg,#fdfefe_0%,#eff6ff_100%)]" />
    <div class="relative min-h-screen flex items-center justify-center px-6">
      <div class="w-full max-w-md rounded-3xl border border-blue-100 bg-white/90 backdrop-blur-xl shadow-[0_24px_80px_rgba(15,23,42,0.10)] p-8">
        <div class="mb-8">
          <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-sky-500 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-200">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h1 class="mt-5 text-2xl font-bold text-slate-900 tracking-tight">VGuard</h1>
          <p class="mt-2 text-sm leading-6 text-slate-500">注册新账号后登录，进入系统演示。</p>
        </div>

        <div class="space-y-3">
          <div class="flex rounded-xl bg-slate-100 p-1">
            <button
              class="flex-1 rounded-lg py-2 text-sm font-medium transition-colors"
              :class="mode === 'login' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'"
              @click="mode = 'login'"
            >
              登录
            </button>
            <button
              class="flex-1 rounded-lg py-2 text-sm font-medium transition-colors"
              :class="mode === 'register' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'"
              @click="mode = 'register'"
            >
              注册
            </button>
          </div>
          <div class="space-y-3">
            <Input v-model="loginUser" placeholder="设置用户名" class="h-11" />
            <Input v-model="loginPass" type="password" placeholder="设置密码" class="h-11" />
          </div>
          <Button v-if="mode === 'login'" class="w-full h-11 bg-sky-600 hover:bg-sky-700" :disabled="loading" @click="submit">
            {{ loading ? '登录中...' : '开始展示' }}
          </Button>
          <Button v-else class="w-full h-11 bg-sky-600 hover:bg-sky-700" :disabled="loading" @click="registerUser">
            {{ loading ? '注册中...' : '创建账号' }}
          </Button>
          <p v-if="loginError" class="text-sm text-red-500">{{ loginError }}</p>
          <p v-if="registerHint" class="text-sm text-sky-600">{{ registerHint }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

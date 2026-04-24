<template>
  <div class="container">
    <div class="header">用户登录</div>

    <div class="content">
      <div class="login-container">
        <h2>用户登录</h2>

        <div class="form-item">
          <label>用户名</label>
          <input
            v-model="form.username"
            placeholder="请输入用户名"
            @keyup.enter="handleLogin"
          />
        </div>

        <div class="form-item">
          <label>密码</label>
          <input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            @keyup.enter="handleLogin"
          />
        </div>

        <button class="btn-login" @click="handleLogin" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>

        <p class="tip">{{ msg }}</p>

        <div class="extra-actions">
          <span>还没有账号？</span>
          <button class="link-btn" @click="goToRegister">去注册</button>
        </div>
      </div>
    </div>

    <BottomNav />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import BottomNav from '../components/BottomNav.vue'

const router = useRouter()

const form = ref({
  username: '',
  password: ''
})

const msg = ref('')
const loading = ref(false)

const goToRegister = () => {
  router.push('/register')
}

const handleLogin = async () => {
  msg.value = ''

  const username = form.value.username.trim()
  const password = form.value.password

  if (!username) {
    msg.value = '请输入用户名'
    return
  }

  if (!password) {
    msg.value = '请输入密码'
    return
  }

  loading.value = true

  try {
  const res = await axios.post('/api/auth/login', {
  username,
  password
})

  console.log('登录返回 data =', res.data)

  const data = res.data

  const accessToken =
    data?.access_token ||
    data?.data?.access_token ||
    data?.token ||
    data?.data?.token

  if (accessToken) {
    localStorage.setItem('access_token', accessToken)
    msg.value = '登录成功，正在跳转...'

    setTimeout(() => {
      router.push('/profile')
    }, 500)
  } else {
    msg.value = '登录失败：后端未返回 token'
    console.log('未识别的登录返回结构：', JSON.stringify(data, null, 2))
  }
} catch (err) {
  console.log('登录失败返回数据：', err.response?.data)

  msg.value =
    err.response?.data?.message ||
    err.response?.data?.detail ||
    err.message ||
    '登录失败'
} finally {
  loading.value = false
}
  
}
</script>

<style scoped>
.login-container {
  width: 100%;
  max-width: 420px;
  margin: 0 auto;
  padding: 30px 20px 20px;
}

.login-container h2 {
  text-align: center;
  margin-bottom: 28px;
  color: #333;
}

.form-item {
  margin-bottom: 18px;
}

.form-item label {
  display: block;
  margin-bottom: 8px;
  font-size: 16px;
  color: #333;
}

.form-item input {
  width: 100%;
  box-sizing: border-box;
  padding: 14px 16px;
  border: 1px solid #ddd;
  border-radius: 10px;
  font-size: 16px;
  outline: none;
  background: #fff;
}

.form-item input:focus {
  border-color: #4caf50;
}

.btn-login {
  width: 100%;
  margin-top: 12px;
  padding: 14px 16px;
  background: #4caf50;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 17px;
  cursor: pointer;
}

.btn-login:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.tip {
  min-height: 24px;
  margin-top: 16px;
  text-align: center;
  color: #f44336;
  font-size: 15px;
}

.extra-actions {
  margin-top: 18px;
  text-align: center;
  color: #666;
  font-size: 14px;
}

.link-btn {
  margin-left: 8px;
  border: none;
  background: transparent;
  color: #4caf50;
  cursor: pointer;
  font-size: 14px;
}
</style>
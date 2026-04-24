<template>
  <!-- 🔥 用全局 container，自动变成 APP 界面 -->
  <div class="container">

    <!-- 🔥 全局头部（和聊天页一模一样） -->
    <div class="header">用户注册</div>

    <!-- 🔥 全局内容区域（自动撑满、可滚动） -->
    <div class="content">
      <div class="register-container">
        <h2>用户注册</h2>

        <div class="form-item">
          <label>用户名</label>
          <input v-model="form.username" placeholder="请输入用户名" />
        </div>

        <div class="form-item">
          <label>密码</label>
          <input v-model="form.password" type="password" placeholder="请输入密码" />
        </div>

        <div class="form-item">
          <label>确认密码</label>
          <input v-model="form.confirm_password" type="password" placeholder="请再次输入密码" />
        </div>

        <div class="form-item">
          <label>邮箱（选填）</label>
          <input v-model="form.email" placeholder="请输入邮箱" />
        </div>

        <div class="form-item">
          <label>手机号（选填）</label>
          <input v-model="form.phone" placeholder="请输入手机号" />
        </div>

        <button class="btn-register" @click="handleRegister">注册</button>
        <p class="tip">{{ msg }}</p>
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
  password: '',
  confirm_password: '',
  email: '',
  phone: ''
})

const msg = ref('')
const loading = ref(false)

const handleRegister = async () => {
  msg.value = ''

  const username = form.value.username.trim()
  const password = form.value.password
  const confirmPassword = form.value.confirm_password
  const email = form.value.email.trim()
  const phone = form.value.phone.trim()

  if (!username) {
    msg.value = '请输入用户名'
    return
  }

  if (password.length < 8) {
    msg.value = '密码至少8位'
    return
  }

  if (password !== confirmPassword) {
    msg.value = '两次密码不一致'
    return
  }

  const payload = {
    username,
    password,
    confirm_password: confirmPassword,
    email,
    phone
  }

  loading.value = true

  try {
    const res = await axios.post('/api/auth/register', payload)

    if (res.data.code === 0) {
      msg.value = res.data.message || '注册成功，正在跳转登录页'
      setTimeout(() => {
        router.push('/login')
      }, 1000)
    } else {
      msg.value = res.data.message || '注册失败'
    }
  } catch (err) {
    msg.value =
      err.response?.data?.message ||
      err.response?.data?.detail ||
      err.message ||
      '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 🔥 只保留你自己的样式，布局全删！全部靠全局！ */

.register-container {
  max-width: 400px;
  margin: 30px auto;
  padding: 30px;
  border: 1px solid #eee;
  border-radius: 8px;
  background: #fff;
}
.form-item {
  margin-bottom: 18px;
}
.form-item label {
  display: block;
  margin-bottom: 6px;
}
.form-item input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-sizing: border-box;
}
.btn-register {
  width: 100%;
  padding: 12px;
  background: #4CAF50;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.tip {
  margin-top: 15px;
  text-align: center;
  color: #f56c6c;
}

:deep(.navbar) {
  flex-shrink: 0;
  height: 50px;
  background: white;
  border-top: 1px solid #eee;
}
</style>
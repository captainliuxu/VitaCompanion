<template>
  <!-- 🔥 只用全局的 container，不自己写样式 -->
  <div class="container">

    <!-- 🔥 全局头部样式，和聊天页一样 -->
    <div class="header">我的</div>

    <!-- 🔥 全局内容区域，自动撑满 -->
    <div class="content">
      <!-- 未登录：显示登录/注册入口 -->
      <div v-if="!token" class="auth-box">
        <h2>请先登录</h2>
        <div class="btn-group">
          <button @click="goToLogin">去登录</button>
          <button @click="goToRegister">去注册</button>
        </div>
      </div>

      <!-- 已登录：显示个人资料 -->
      <div v-else class="profile-content">
        <div class="card">疾病：高血压</div>
        <div class="card">
          用药计划：<br>
          早 8:00<br>
          晚 8:00
        </div>
        <div class="card">
          检测计划：<br>
          每晚测一次血压
        </div>
        <div class="card">
          建议：<br>
          低盐饮食、规律作息、适量运动
        </div>

        <div class="user-info">
          <h2>我的资料</h2>
          <p>用户名：{{ username }}</p>
          <p>邮箱：{{ email }}</p>
          <button @click="logout">退出登录</button>
        </div>
      </div>
    </div>

    <!-- 底部导航不动 -->
    <BottomNav />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import BottomNav from '../components/BottomNav.vue'

const router = useRouter()

// 检测登录状态
const token = ref(localStorage.getItem('access_token'))
const username = ref('')
const email = ref('')

// 跳转方法
const goToLogin = () => router.push('/login')
const goToRegister = () => router.push('/register')

// 退出登录
const logout = () => {
  localStorage.removeItem('access_token')
  token.value = null
  alert('退出成功')
  router.push('/login')
}

// 页面加载获取用户信息
onMounted(() => {
  if (token.value) {
    username.value = '你的用户名'
    email.value = '你的邮箱'
  }
})
</script>

<style scoped>

.auth-box {
  text-align: center;
  padding-top: 100px;
}
.auth-box h2 {
  margin-bottom: 30px;
  color: #333;
}
.btn-group {
  display: flex;
  gap: 20px;
  justify-content: center;
}
.btn-group button {
  padding: 12px 30px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
}

.profile-content .card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 15px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  font-size: 16px;
  line-height: 1.6;
}

.user-info {
  text-align: center;
  margin-top: 30px;
  padding: 20px;
  background: white;
  border-radius: 12px;
}
.user-info button {
  margin-top: 15px;
  padding: 10px 25px;
  background: #f44336;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

:deep(.navbar) {
  flex-shrink: 0;
  height: 50px;
  background: white;
  border-top: 1px solid #eee;
}
</style>

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

  <p>用户名：{{ username || '未填写' }}</p>
  <p>邮箱：{{ email || '未填写' }}</p>

  <div class="profile-actions">
    <button class="logout-btn" @click="logout">退出登录</button>
    <button class="edit-btn" @click="openEditDialog">修改资料</button>
  </div>
</div>

<!-- 修改资料悬浮窗口 -->
<div v-if="showEditDialog" class="modal-mask">
  <div class="modal-box">
    <h2>修改资料</h2>

    <div class="info-row" @click="editingField = 'username'">
      <span>用户名</span>
      <input
        v-if="editingField === 'username'"
        v-model="editForm.username"
        class="plain-input"
        autofocus
      />
      <strong v-else>{{ editForm.username || '未填写' }}</strong>
    </div>

    <div class="info-row" @click="editingField = 'email'">
      <span>邮箱</span>
      <input
        v-if="editingField === 'email'"
        v-model="editForm.email"
        class="plain-input"
      />
      <strong v-else>{{ editForm.email || '未填写' }}</strong>
    </div>

    <div class="info-row" @click="editingField = 'password'">
      <span>密码</span>
      <input
        v-if="editingField === 'password'"
        v-model="editForm.password"
        type="password"
        class="plain-input"
        placeholder="输入新密码"
      />
      <strong v-else>********</strong>
    </div>

    <div class="modal-actions">
      <button class="cancel-btn" @click="closeEditDialog">取消</button>
      <button class="save-btn" @click="updateUser">保存</button>
    </div>
  </div>
</div>
      </div>
    </div>

    <!-- 底部导航不动 -->
    <BottomNav />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import BottomNav from '../components/BottomNav.vue'

const router = useRouter()

const token = ref(localStorage.getItem('access_token'))
const username = ref('')
const email = ref('')

const showEditDialog = ref(false)
const editingField = ref('')

const editForm = ref({
  username: '',
  email: '',
  password: ''
})

const goToLogin = () => router.push('/login')
const goToRegister = () => router.push('/register')

const logout = () => {
  localStorage.removeItem('access_token')
  token.value = null
  alert('退出成功')
  router.push('/login')
}

const loadUserInfo = async () => {
  if (!token.value) return

  try {
    const res = await axios.get('/api/users/me', {
      headers: {
        Authorization: `Bearer ${token.value}`
      }
    })
   console.log('用户信息返回：', res.data)
    const data = res.data.data || res.data

    username.value = data.username || ''
    email.value = data.email || ''
  } catch (err) {
    console.log('获取用户信息失败：', err.response?.data || err)
  }
}

const openEditDialog = () => {
  editForm.value.username = username.value
  editForm.value.email = email.value
  editForm.value.password = ''
  editingField.value = ''
  showEditDialog.value = true
}

const closeEditDialog = () => {
  showEditDialog.value = false
  editingField.value = ''
}

const updateUser = async () => {
  try {
    const payload = {
      username: editForm.value.username,
      email: editForm.value.email
    }

    if (editForm.value.password) {
      payload.password = editForm.value.password
    }

    const res = await axios.put('/api/users/me', payload, {
      headers: {
        Authorization: `Bearer ${token.value}`
      }
    })

    const data = res.data.data || res.data

    username.value = data.username || editForm.value.username
    email.value = data.email || editForm.value.email

    alert('修改成功')
    closeEditDialog()
  } catch (err) {
    console.log('修改资料失败：', err.response?.data || err)
    alert(err.response?.data?.message || err.response?.data?.detail || '修改失败')
  }
}

onMounted(() => {
  loadUserInfo()
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
.profile-actions {
  display: flex;          /* 启用 Flex 布局 */
  justify-content: center;/* 子元素整体水平居中 */
  gap: 16px;              /* 两个按钮之间的间距，可自行调整数值 */
  /* 如果父容器没有默认宽度，可以加上：width: 100%; */
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

.profile-actions {
  display: flex;
  justify-content: center;
  gap: 22px;
  margin-top: 24px;
}

.logout-btn,
.edit-btn {
  padding: 10px 26px;
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 15px;
}

.logout-btn {
  background: #f44336;
}

.edit-btn {
  background: #4caf50;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-box {
  width: 70%;
  max-width: 300px;
  background: #fff;
  border-radius: 18px;
  padding: 24px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

.modal-box h2 {
  text-align: center;
  margin-bottom: 22px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 0;
  border-bottom: 1px solid #eee;
  font-size: 16px;
}

.info-row span {
  color: #666;
}

.info-row strong {
  color: #222;
}

.plain-input {
  border: none;
  outline: none;
  background: transparent;
  text-align: right;
  font-size: 16px;
  max-width: 190px;
}

.modal-actions {
  display: flex;
  gap: 16px;
  margin-top: 24px;
}

.cancel-btn,
.save-btn {
  flex: 1;
  padding: 11px 0;
  border: none;
  border-radius: 10px;
  color: white;
  font-size: 15px;
}

.cancel-btn {
  background: #999;
}

.save-btn {
  background: #4caf50;
}
</style>
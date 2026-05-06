<template>
  <div class="container">
    <div class="header">健康档案</div>

    <div class="content">
      <div class="profile-card">
        <h2>我的健康档案</h2>
        <p class="sub-title">完善基础信息，帮助健康助手给出更合适的建议</p>

        <div class="form-item">
          <label>姓名 <span class="required">*</span></label>
          <input v-model="form.name" placeholder="请输入姓名" />
        </div>

        <div class="form-row">
          <div class="form-item">
            <label>年龄</label>
            <input 
              v-model="form.age" 
              type="number" 
              placeholder="岁" 
              min="0"
              max="150"
            />
          </div>

          <div class="form-item">
            <label>性别 <span class="required">*</span></label>
            <select v-model="form.gender">
              <option value="">请选择</option>
              <option value="male">男</option>
              <option value="female">女</option>
              <option value="other">其他</option>
            </select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-item">
            <label>身高</label>
            <input 
              v-model="form.height" 
              type="number" 
              placeholder="cm" 
              min="0"
              max="300"
            />
          </div>

          <div class="form-item">
            <label>体重</label>
            <input 
              v-model="form.weight" 
              type="number" 
              placeholder="kg" 
              min="0"
              max="500"
            />
          </div>
        </div>

        <div class="form-item">
          <label>慢病史</label>
          <textarea 
            v-model="form.chronic_diseases" 
            placeholder="例如：高血压、糖尿病、哮喘"
          ></textarea>
        </div>

        <div class="form-item">
          <label>过敏史</label>
          <textarea 
            v-model="form.allergies" 
            placeholder="例如：青霉素过敏、花粉过敏、无"
          ></textarea>
        </div>

        <button 
          class="save-btn" 
          @click="saveProfile" 
          :disabled="loading"
        >
          {{ loading ? '保存中...' : '保存健康档案' }}
        </button>

        <p class="tip" :class="{ success: isSuccess }">{{ msg }}</p>
      </div>
    </div>

    <BottomNav />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import BottomNav from '../components/BottomNav.vue'

// 全局token
const token = localStorage.getItem('access_token')

// 状态变量
const loading = ref(false)
const msg = ref('')
const isSuccess = ref(false)

// 表单数据
const form = ref({
  name: '',
  age: '',
  gender: '',
  height: '',
  weight: '',
  chronic_diseases: '',
  allergies: ''
})

// 请求头封装
const getAuthHeaders = () => {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token || ''}`
  }
}

// 表单基础校验
const checkForm = () => {
  if (!form.value.name.trim()) {
    msg.value = '请输入姓名'
    isSuccess.value = false
    return false
  }
  if (!form.value.gender) {
    msg.value = '请选择性别'
    isSuccess.value = false
    return false
  }
  return true
}

// 加载用户档案
const loadProfile = async () => {
  if (!token) {
    msg.value = '请先登录'
    isSuccess.value = false
    return
  }

  try {
    const res = await fetch('/api/profiles/me', {
      method: 'GET',
      headers: getAuthHeaders()
    })

    const payload = await res.json()
    if (res.ok && payload.code === 0) {
      const data = payload.data || {}
      form.value = {
        name: data.name || '',
        age: data.age ?? '',
        gender: data.gender || '',
        height: data.height ?? '',
        weight: data.weight ?? '',
        chronic_diseases: data.chronic_diseases || '',
        allergies: data.allergies || ''
      }
    }
  } catch (err) {
    console.error('读取健康档案失败：', err)
  }
}

// 保存档案（存在更新/不存在新建）
const saveProfile = async () => {
  // 前置校验
  if (!token) {
    msg.value = '请先登录'
    isSuccess.value = false
    return
  }
  if (!checkForm()) return

  loading.value = true
  msg.value = ''
  isSuccess.value = false

  // 格式化提交数据
  const payload = {
    name: form.value.name.trim(),
    age: form.value.age ? Number(form.value.age) : null,
    gender: form.value.gender,
    height: form.value.height ? Number(form.value.height) : null,
    weight: form.value.weight ? Number(form.value.weight) : null,
    chronic_diseases: form.value.chronic_diseases.trim(),
    allergies: form.value.allergies.trim()
  }

  try {
    let res = await fetch('/api/profiles/me', {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload)
    })

    // 404则新建数据
    if (res.status === 404) {
      res = await fetch('/api/profiles/me', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      })
    }

    const data = await res.json()
    if (res.ok && data.code === 0) {
      msg.value = '保存成功'
      isSuccess.value = true
    } else {
      msg.value = data.message || '保存失败'
      isSuccess.value = false
    }
  } catch (err) {
    console.error('保存健康档案失败：', err)
    msg.value = '保存失败，请检查网络或后端服务'
    isSuccess.value = false
  } finally {
    loading.value = false
  }
}

// 页面挂载加载数据
onMounted(() => {
  loadProfile()
})
</script>

<style scoped>
.profile-card {
  max-width: 420px;
  margin: 24px auto;
  padding: 26px 22px;
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06);
}

.profile-card h2 {
  text-align: center;
  margin-bottom: 8px;
  color: #222;
}

.sub-title {
  text-align: center;
  font-size: 14px;
  color: #777;
  margin-bottom: 24px;
}

.form-row {
  display: flex;
  gap: 14px;
}

.form-row .form-item {
  flex: 1;
}

.form-item {
  margin-bottom: 18px;
}

.form-item label {
  display: block;
  margin-bottom: 8px;
  font-size: 15px;
  color: #333;
}

.required {
  color: #f44336;
  margin-left: 2px;
}

.form-item input,
.form-item select,
.form-item textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 13px 14px;
  border: 1px solid #ddd;
  border-radius: 12px;
  font-size: 15px;
  outline: none;
  background: #fff;
  transition: border-color 0.2s;
}

.form-item textarea {
  min-height: 82px;
  resize: none;
  line-height: 1.5;
}

.form-item input:focus,
.form-item select:focus,
.form-item textarea:focus {
  border-color: #4caf50;
}

.save-btn {
  width: 100%;
  margin-top: 10px;
  padding: 14px;
  background: #4caf50;
  color: white;
  border: none;
  border-radius: 14px;
  font-size: 16px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.save-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.tip {
  min-height: 24px;
  margin-top: 15px;
  text-align: center;
  color: #f44336;
  font-size: 14px;
  margin: 15px 0 0;
}

.tip.success {
  color: #4caf50;
}
</style>
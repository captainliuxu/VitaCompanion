<template>
  <div class="container">
    <div class="header">健康助手</div>

    <div class="content chat-page">
      <div class="chat-panel">
        <div class="chat-topbar">
          <div class="chat-title">智能健康对话</div>
          <div class="chat-subtitle">记录状态、咨询问题、获取建议</div>
        </div>

        <div class="messages">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="[
              'message-row',
              msg.role === 'user' ? 'message-row-user' : 'message-row-ai'
            ]"
          >
            <div class="avatar" :class="msg.role === 'user' ? 'avatar-user' : 'avatar-ai'">
              {{ msg.role === 'user' ? '我' : 'AI' }}
            </div>

            <div
              :class="[
                'message-bubble',
                msg.role === 'user' ? 'user-message' : 'ai-message'
              ]"
            >
              {{ msg.content }}
            </div>
          </div>
        </div>

        <div class="quick-tips">
          <span class="quick-tag">血压</span>
          <span class="quick-tag">服药</span>
          <span class="quick-tag">头晕</span>
          <span class="quick-tag">睡眠</span>
        </div>

        <div class="input-area">
          <input
            v-model="inputText"
            @keyup.enter="handleSend"
            placeholder="输入消息..."
            class="input"
          />
          <button @click="handleSend" class="send-btn">发送</button>
        </div>

        <button @click="triggerProactiveMessage" class="proactive-btn">主动提醒</button>
      </div>
    </div>

    <BottomNav />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import BottomNav from '../components/BottomNav.vue'
import { sendChatMessage } from '../api/chat'
import { listConversations, createConversation } from '../api/conversation'
import { listMessages } from '../api/message'

const conversationId = ref(null)
const inputText = ref('')
const messages = ref([])

const proactiveMessages = [
  '现在是晚间服药时间，记得按计划完成用药。',
  '你今天还没有记录血压，建议今晚尽快测量一次。',
  '你最近提到过头晕，今晚注意休息，并留意身体状态。',
  '慢病管理最重要的是长期规律，坚持记录会更有帮助。'
]

function triggerProactiveMessage() {
  const randomIndex = Math.floor(Math.random() * proactiveMessages.length)
  messages.value.push({
    role: 'assistant',
    content: proactiveMessages[randomIndex]
  })
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text) return

  messages.value.push({
    role: 'user',
    content: text
  })

  inputText.value = ''

  try {
    const data = await sendChatMessage(conversationId.value, text)
    messages.value.push({
      role: 'assistant',
      content: data.reply
    })
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: '后端连接失败，请确认 FastAPI 已启动'
    })
  }
}

onMounted(() => {
  console.log('ChatView 进来了')
})

onMounted(async () => {
  const token = localStorage.getItem('access_token')
  /*if (!token) {
    alert('请先登录')
    return
  }*/

  const listData = await listConversations()

  if (listData.items.length > 0) {
    conversationId.value = listData.items[0].id
  } else {
    const conversation = await createConversation({ title: '新的健康咨询' })
    conversationId.value = conversation.id
  }

  const messageData = await listMessages(conversationId.value)

  messages.value = messageData.items.map(msg => ({
    role: msg.role,
    content: msg.content
  }))
})
</script>

<style scoped>
.chat-page {
  padding: 14px;
  box-sizing: border-box;
}

.chat-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #f8fff8 0%, #f4f6f8 100%);
  border-radius: 20px;
  padding: 14px;
  box-sizing: border-box;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.05);
}

.chat-topbar {
  background: linear-gradient(135deg, #5fcf65 0%, #43b649 100%);
  color: white;
  border-radius: 16px;
  padding: 14px 16px;
  margin-bottom: 14px;
  box-shadow: 0 4px 14px rgba(76, 175, 80, 0.25);
}

.chat-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 4px;
}

.chat-subtitle {
  font-size: 13px;
  opacity: 0.92;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 6px 2px;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.message-row-ai {
  justify-content: flex-start;
}

.message-row-user {
  justify-content: flex-end;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.avatar-ai {
  background: #e8f5e9;
  color: #2e7d32;
  border: 1px solid #c8e6c9;
}

.avatar-user {
  background: #e3f2fd;
  color: #1565c0;
  border: 1px solid #bbdefb;
}

.message-bubble {
  padding: 12px 14px;
  border-radius: 18px;
  max-width: 78%;
  word-break: break-word;
  line-height: 1.6;
  font-size: 15px;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.04);
}

.ai-message {
  background: #ffffff;
  color: #333;
  border: 1px solid #eef1f4;
  border-bottom-left-radius: 8px;
}

.user-message {
  background: linear-gradient(135deg, #66bb6a 0%, #4caf50 100%);
  color: #fff;
  border-bottom-right-radius: 8px;
}

.quick-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.quick-tag {
  padding: 6px 12px;
  background: #ffffff;
  border: 1px solid #e7ebef;
  border-radius: 999px;
  font-size: 12px;
  color: #666;
}

.input-area {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.input {
  flex: 1;
  padding: 13px 16px;
  border: 1px solid #dfe5e9;
  border-radius: 16px;
  font-size: 15px;
  outline: none;
  background: #fff;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input:focus {
  border-color: #4caf50;
  box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.12);
}

.send-btn {
  padding: 12px 18px;
  min-width: 72px;
  background: linear-gradient(135deg, #4caf50 0%, #43a047 100%);
  color: white;
  border: none;
  border-radius: 16px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(76, 175, 80, 0.22);
}

.proactive-btn {
  width: 100%;
  padding: 13px;
  background: linear-gradient(135deg, #ffa726 0%, #fb8c00 100%);
  color: white;
  border: none;
  border-radius: 16px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(251, 140, 0, 0.22);
}
</style>
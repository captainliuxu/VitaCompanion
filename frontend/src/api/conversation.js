export async function listConversations() {
  const token = localStorage.getItem('access_token')

  const res = await fetch('/api/conversations', {
    headers: {
      Authorization: `Bearer ${token}`
    }
  })

  const payload = await res.json()

  if (!res.ok || payload.code !== 0) {
    throw new Error(payload.message || '获取会话列表失败')
  }

  return payload.data
}

export async function createConversation(payload = {}) {
  const token = localStorage.getItem('access_token')

  const res = await fetch('/api/conversations', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  })

  const data = await res.json()

  if (!res.ok || data.code !== 0) {
    throw new Error(data.message || '创建会话失败')
  }

  return data.data
}
export async function sendChatMessage(conversationId, content) {
  const token = localStorage.getItem('access_token')

  const res = await fetch('/api/chat/send', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      content
    })
  })

  const payload = await res.json()

  if (!res.ok || payload.code !== 0) {
    throw new Error(payload.message || '发送消息失败')
  }

  return payload.data
}
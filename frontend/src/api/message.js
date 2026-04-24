export async function listMessages(conversationId) {
  const token = localStorage.getItem('access_token')

  const res = await fetch(`/api/conversations/${conversationId}/messages`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  })

  const payload = await res.json()

  if (!res.ok || payload.code !== 0) {
    throw new Error(payload.message || '获取消息失败')
  }

  return payload.data
}
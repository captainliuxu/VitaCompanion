export async function sendChatMessageStream(conversationId, content, onChunk) {
  const token = localStorage.getItem('access_token')

  const res = await fetch('/api/chat/send-stream', {
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

  if (!res.ok) {
    throw new Error('流式请求失败')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

   const chunk = decoder.decode(value, { stream: true })
console.log('原始流 chunk =', chunk)

buffer += chunk

const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const text = line.trim()

      if (!text) continue

      if (text.startsWith('data:')) {
  const data = text.replace(/^data:\s*/, '')

  if (!data || data === '[DONE]') continue

  try {
    const json = JSON.parse(data)

    // ✅ 只取真正内容
    if (json.event === 'token' && json.token) {
      onChunk(json.token)
    }


  } catch (e) {
    // fallback（防炸）
    onChunk(data)
  }
} else {
        onChunk(text)
      }
    }
  }

  if (buffer.trim()) {
    const text = buffer.trim()
    if (text.startsWith('data:')) {
      onChunk(text.replace(/^data:\s*/, ''))
    } else {
      onChunk(text)
    }
  }
}
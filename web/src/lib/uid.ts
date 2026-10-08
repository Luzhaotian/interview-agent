/**
 * 生成消息/会话 id。
 * crypto.randomUUID 只在安全上下文（https 或 localhost）可用；
 * 用局域网 IP 打开 dev server 时它是 undefined，直接调用会抛错。
 * 这里做降级，保证任何环境都能拿到唯一 id。
 */
export function uid(): string {
  const cryptoObj = globalThis.crypto
  if (cryptoObj && typeof cryptoObj.randomUUID === 'function') {
    return cryptoObj.randomUUID()
  }
  // 降级：优先用 getRandomValues，再退回时间戳+随机数
  if (cryptoObj && typeof cryptoObj.getRandomValues === 'function') {
    const bytes = new Uint8Array(16)
    cryptoObj.getRandomValues(bytes)
    return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

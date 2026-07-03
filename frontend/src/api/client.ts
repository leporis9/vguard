function getBase() {
  return localStorage.getItem('vguard_server') || ''
}

export async function apiFetch<T = any>(url: string, init?: RequestInit): Promise<T> {
  const fullUrl = (getBase() && !url.startsWith('http')) ? getBase() + url : url
  const resp = await fetch(fullUrl, init)
  const text = await resp.text()
  const data = text ? JSON.parse(text) : {}
  if (!resp.ok) {
    throw new Error(data?.message || data?.error || `HTTP ${resp.status}`)
  }
  if (data?.success === false) {
    throw new Error(data?.message || data?.error || 'Request failed')
  }
  return data as T
}

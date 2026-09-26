import { apiFetch } from './client'
import type { MissionInstance, TokenResponse, Track, User } from './types'

export const api = {
  register: (body: { email: string; password: string; display_name: string; track?: Track }) =>
    apiFetch<User>('/auth/register', { method: 'POST', body: JSON.stringify(body) }),

  login: (body: { email: string; password: string }) =>
    apiFetch<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify(body) }),

  me: () => apiFetch<User>('/user/me'),

  updateMe: (body: Partial<Omit<User, 'id' | 'email'>>) =>
    apiFetch<User>('/user/me', { method: 'PATCH', body: JSON.stringify(body) }),

  missions: (date: string = 'today') =>
    apiFetch<MissionInstance[]>(`/missions?date=${encodeURIComponent(date)}`),

  mission: (id: string) => apiFetch<MissionInstance>(`/missions/${encodeURIComponent(id)}`),
}

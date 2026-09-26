import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { MissionCard } from './components/MissionCard'
import type { MissionInstance, User } from './api/types'
import { AuthProvider } from './hooks/useAuth'

const user: User = {
  id: 'u1',
  email: 'recruit@example.com',
  display_name: 'Recruit',
  time_zone: 'UTC',
  track: 'general',
  language_level_hebrew: 0,
  language_level_arabic: 0,
  language_level_farsi: 0,
  fitness_target_hr_zone: 2,
  fitness_daily_kcal_goal: 300,
  program_start_date: '2026-09-23',
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function mockApi(routes: Record<string, unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const key = Object.keys(routes).find((k) => url.includes(k))
      return key
        ? new Response(JSON.stringify(routes[key]), { status: 200 })
        : new Response('{"detail":"Not found"}', { status: 404 })
    }),
  )
}

describe('routing', () => {
  beforeEach(() => sessionStorage.clear())
  afterEach(() => vi.unstubAllGlobals())

  it('sends unauthenticated visitors to the login page', async () => {
    renderAt('/dashboard')
    expect(await screen.findByText('Identify yourself, recruit.')).toBeInTheDocument()
  })

  it('shows the dashboard with an empty-state message for a signed-in recruit', async () => {
    sessionStorage.setItem('midrasha.token', 'test-token')
    mockApi({ '/api/user/me': user, '/api/missions?date=today': [] })
    renderAt('/dashboard')
    expect(await screen.findByText("Today's briefing")).toBeInTheDocument()
    expect(await screen.findByText(/No missions assigned yet/)).toBeInTheDocument()
    expect(screen.getByText(/Fictional training simulation/)).toBeInTheDocument()
  })

  it('renders the settings page', async () => {
    sessionStorage.setItem('midrasha.token', 'test-token')
    mockApi({ '/api/user/me': user })
    renderAt('/settings')
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()
  })
})

describe('MissionCard', () => {
  it('shows name, type, status and an RTL-capable title', () => {
    const mission: MissionInstance = {
      id: 'm1',
      mission_template_id: 't1',
      scheduled_date: '2026-01-05',
      status: 'assigned',
      template: {
        id: 't1',
        name: 'אלף-בית',
        description: 'Learn the first five Hebrew letters.',
        type: 'language',
        skill_tags: ['hebrew_alphabet'],
        day_offset: 1,
        phase: null,
        difficulty: 1,
        required_resource_ids: [],
      },
    }
    render(
      <MemoryRouter>
        <MissionCard mission={mission} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'אלף-בית' })).toHaveAttribute('dir', 'auto')
    expect(screen.getByText('language')).toBeInTheDocument()
    expect(screen.getByText('Assigned')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open mission' })).toHaveAttribute('href', '/mission/m1')
  })
})

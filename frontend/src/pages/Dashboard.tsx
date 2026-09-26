import { api } from '../api/endpoints'
import { MissionCard } from '../components/MissionCard'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'

export function Dashboard() {
  const { user } = useAuth()
  const { data: missions, error, loading } = useAsync(() => api.missions('today'), [])

  return (
    <section>
      <h1>Today's briefing</h1>
      <p className="muted">Recruit {user?.display_name}. Your orders for today:</p>
      {loading && <p className="muted">Loading missions…</p>}
      {error && <p className="error">Could not load missions: {error.message}</p>}
      {missions?.length === 0 && (
        <p className="muted">No missions assigned yet. The recruiter will be in touch.</p>
      )}
      <div className="grid">
        {missions?.map((m) => <MissionCard key={m.id} mission={m} />)}
      </div>
    </section>
  )
}

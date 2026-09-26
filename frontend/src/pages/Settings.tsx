import { useAuth } from '../hooks/useAuth'

export function Settings() {
  const { user } = useAuth()
  return (
    <section>
      <h1>Settings</h1>
      <p className="muted">Editable time zone, language emphasis and fitness baseline coming next.</p>
      {user && (
        <dl className="facts">
          <dt>Time zone</dt>
          <dd>{user.time_zone}</dd>
          <dt>Track</dt>
          <dd>{user.track}</dd>
          <dt>Hebrew / Arabic / Farsi</dt>
          <dd>
            {user.language_level_hebrew} / {user.language_level_arabic} /{' '}
            {user.language_level_farsi}
          </dd>
          <dt>Fitness target</dt>
          <dd>
            HR zone {user.fitness_target_hr_zone} · {user.fitness_daily_kcal_goal} kcal/day
          </dd>
        </dl>
      )}
    </section>
  )
}

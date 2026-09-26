// Mirrors backend Pydantic schemas (backend/app/schemas). Keep in sync by hand for now.

export type Track = 'cyber' | 'osint' | 'journalist' | 'general'
export type MissionType = 'language' | 'fitness' | 'study' | 'osint' | 'scenario'
export type MissionStatus = 'assigned' | 'in_progress' | 'completed' | 'failed'
export type Phase = 'induction' | 'specialisation' | 'operations'

export interface User {
  id: string
  email: string
  display_name: string
  time_zone: string
  track: Track
  language_level_hebrew: number
  language_level_arabic: number
  language_level_farsi: number
  fitness_target_hr_zone: number
  fitness_daily_kcal_goal: number
  program_start_date: string
}

export interface MissionTemplate {
  id: string
  name: string
  description: string
  type: MissionType
  skill_tags: string[]
  day_offset: number | null
  phase: Phase | null
  difficulty: number
  required_resource_ids: string[]
}

export interface MissionInstance {
  id: string
  mission_template_id: string
  scheduled_date: string
  status: MissionStatus
  template: MissionTemplate
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
}

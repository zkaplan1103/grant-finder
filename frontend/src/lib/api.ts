// Mirrors the backend Profile (request) and FullResult (response) contracts.

export interface Profile {
  org_basics: { is_501c3: boolean; annual_budget_usd: number; org_age_years: number }
  project_type: string
  funding_preference: 'grant' | 'loan' | 'either'
  geography?: { state?: string; service_area?: string; disadvantaged_community?: boolean | null }
  project?: {
    project_type?: string; size_kw?: number; estimated_cost_usd?: number
    stage?: string; amount_needed_usd?: number
  }
  mission?: { mission_statement?: string; populations_served?: string[] }
}

export interface Opportunity {
  id: string
  source: string
  title: string
  agency?: string | null
  url?: string | null
  status?: string | null
  close_date?: string | null
  typical_award?: string | null
  eligibility_notes?: string | null
  description?: string | null
}

export interface Match {
  opportunity_id: string
  fit_score: number
  reasoning: string
  low_confidence: boolean
  caveats: string[]
}

export interface UnsupportedClaim { claim: string; reason: string }

export interface Draft {
  status: 'draft' | 'verified' | 'needs_human'
  revision: number
  eligibility_summary: string
  boilerplate: string
  unresolved_claims: UnsupportedClaim[]
}

export interface MatchedOpportunity {
  opportunity: Opportunity
  match: Match
  draft: Draft | null
}

export interface MatchResult {
  profile_sparse: boolean
  grants_gov_ok: boolean
  grants_gov_message: string | null
  matches: MatchedOpportunity[]
}

export interface Progress { stage: string; done: number; total: number }

// Streams progress events, resolves with the final result. onProgress fires per event.
export async function streamMatch(
  profile: Profile,
  onProgress: (p: Progress) => void,
): Promise<MatchResult> {
  const resp = await fetch('/api/match/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
  if (!resp.ok || !resp.body) {
    const body = await resp.json().catch(() => ({ error: 'Request failed.' }))
    throw new Error(body.error || 'Request failed.')
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: MatchResult | null = null
  let error: string | null = null

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const chunk of chunks) {
      const evLine = chunk.match(/^event: (.+)$/m)?.[1]
      const dataLine = chunk.match(/^data: (.+)$/m)?.[1]
      if (!evLine || !dataLine) continue
      const data = JSON.parse(dataLine)
      if (evLine === 'progress') onProgress(data as Progress)
      else if (evLine === 'done') result = data as MatchResult
      else if (evLine === 'error') error = data.error
    }
  }

  if (error) throw new Error(error)
  if (!result) throw new Error('No result received.')
  return result
}

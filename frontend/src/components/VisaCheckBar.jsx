import { useState } from 'react'

export default function VisaCheckBar({ selectedJobs }) {
  const [cap, setCap] = useState(20)
  const [committed, setCommitted] = useState(0)
  const [results, setResults] = useState(null)
  const [checking, setChecking] = useState(false)

  async function runCheck() {
    if (selectedJobs.length === 0) return
    setChecking(true)
    try {
      const res = await fetch('/api/visa-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          weekly_hour_cap: Number(cap),
          committed_hours_elsewhere: Number(committed),
          candidate_listing_ids: selectedJobs.map(j => j.listing_id),
        }),
      })
      const data = await res.json()
      setResults(data.results)
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="feature-bar">
      <div className="feature-bar-header">
        <h2>Visa work-hour guardrail</h2>
      </div>
      <p className="helper-text" style={{ marginTop: -4, marginBottom: 10 }}>
        Most student visas cap term-time work at a fixed number of hours a week. Select
        listings below with "Select", then check whether they'd push you over your cap.
      </p>

      <div className="feature-inputs">
        <div className="field">
          <label>Weekly hour cap</label>
          <input type="number" min="0" value={cap} onChange={e => setCap(e.target.value)} />
        </div>
        <div className="field">
          <label>Hours already committed elsewhere</label>
          <input type="number" min="0" value={committed} onChange={e => setCommitted(e.target.value)} />
        </div>
        <button className="btn primary" disabled={selectedJobs.length === 0 || checking} onClick={runCheck}>
          {checking ? 'Checking…' : `Check ${selectedJobs.length || ''} selected`}
        </button>
      </div>

      {selectedJobs.length === 0 && (
        <p className="helper-text">Select one or more listings below to check them.</p>
      )}

      {results && (
        <div className="result-strip">
          {results.map(r => (
            <div key={r.listing_id} className={`result-row ${r.over_cap ? 'warn' : 'ok'}`}>
              <strong>{r.title}</strong>
              <span>~{r.estimated_weekly_hours}h/wk → {r.projected_total_hours}h total</span>
              <span className="guidance">{r.guidance}</span>
            </div>
          ))}
        </div>
      )}

      <p className="helper-text">
        Estimates only — always confirm your specific visa's rules with your university's
        international student office before accepting a role.
      </p>
    </div>
  )
}

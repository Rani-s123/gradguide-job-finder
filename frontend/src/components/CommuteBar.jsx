import { useState } from 'react'

// Demo preset standing in for a real address autocomplete/geocode call.
// "Main Campus" matches a coordinate the backend already knows about.
const PRESETS = {
  'Main Campus, Riverdale': { lat: 40.700, lng: -74.010 },
  'North Campus, Riverdale': { lat: 40.706, lng: -74.015 },
  'Downtown Riverdale': { lat: 40.712, lng: -74.006 },
}

export default function CommuteBar({ selectedJobs }) {
  const [address, setAddress] = useState('Main Campus, Riverdale')
  const [results, setResults] = useState(null)
  const [checking, setChecking] = useState(false)

  async function runCheck() {
    if (selectedJobs.length === 0) return
    const coords = PRESETS[address]
    if (!coords) return
    setChecking(true)
    try {
      const res = await fetch('/api/commute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_lat: coords.lat,
          student_lng: coords.lng,
          listing_ids: selectedJobs.map(j => j.listing_id),
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
        <h2>Commute &amp; campus proximity</h2>
      </div>
      <p className="helper-text" style={{ marginTop: -4, marginBottom: 10 }}>
        Many international students don't have a car in their first term. Compare walk
        and transit time from a home base to each selected listing.
      </p>

      <div className="feature-inputs">
        <div className="field" style={{ width: 220 }}>
          <label>Home base</label>
          <select className="sort-select" value={address} onChange={e => setAddress(e.target.value)}>
            {Object.keys(PRESETS).map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <button className="btn primary" disabled={selectedJobs.length === 0 || checking} onClick={runCheck}>
          {checking ? 'Calculating…' : `Check ${selectedJobs.length || ''} selected`}
        </button>
      </div>

      {selectedJobs.length === 0 && (
        <p className="helper-text">Select one or more listings below to check them.</p>
      )}

      {results && (
        <div className="result-strip">
          {results.map(r => (
            <div key={r.listing_id} className="result-row">
              <strong>{r.title}</strong>
              {r.distance_km != null ? (
                <span>{r.distance_km} km · {r.walk_minutes} min walk · {r.transit_minutes} min transit</span>
              ) : (
                <span className="guidance">{r.note}</span>
              )}
            </div>
          ))}
        </div>
      )}

      <p className="helper-text">
        Demo uses a small set of known campus/city coordinates. In production this calls
        a real geocoding API for any address the student enters.
      </p>
    </div>
  )
}

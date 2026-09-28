import { useEffect, useMemo, useState } from 'react'
import Filters from './components/Filters.jsx'
import JobList from './components/JobList.jsx'
import VisaCheckBar from './components/VisaCheckBar.jsx'
import CommuteBar from './components/CommuteBar.jsx'

const JOB_TYPES = ['part-time', 'full-time', 'internship', 'casual']

export default function App() {
  const [meta, setMeta] = useState(null)
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const [query, setQuery] = useState('')
  const [activeTypes, setActiveTypes] = useState([])
  const [visaOnly, setVisaOnly] = useState(false)
  const [minTrust, setMinTrust] = useState(0)
  const [sort, setSort] = useState('posted_date')

  const [activeTool, setActiveTool] = useState(null) // 'visa' | 'commute' | null
  const [selectedIds, setSelectedIds] = useState([])

  useEffect(() => {
    fetch('/api/meta').then(r => r.json()).then(setMeta).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (activeTypes.length) params.set('job_type', activeTypes.join(','))
    if (visaOnly) params.set('visa_friendly_only', 'true')
    if (minTrust > 0) params.set('min_trust_score', String(minTrust))
    params.set('sort', sort)
    params.set('order', sort === 'posted_date' ? 'desc' : 'desc')
    params.set('limit', '100')

    const t = setTimeout(() => {
      fetch(`/api/jobs?${params.toString()}`)
        .then(r => r.json())
        .then(data => {
          setJobs(data.results)
          setTotal(data.total)
          setLoading(false)
        })
        .catch(() => setLoading(false))
    }, 200) // debounce keyword typing

    return () => clearTimeout(t)
  }, [query, activeTypes, visaOnly, minTrust, sort])

  function toggleType(t) {
    setActiveTypes(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t])
  }

  function toggleSelected(id) {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const selectedJobs = useMemo(
    () => jobs.filter(j => selectedIds.includes(j.listing_id)),
    [jobs, selectedIds]
  )

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="wordmark">GradGuide <span>Jobs</span></div>
        <div className="tagline">Part-time, full-time & internship roles for international students — scraped straight from campus boards, local chains, and city listings.</div>
      </header>

      <div className="layout">
        <Filters
          jobTypes={JOB_TYPES}
          activeTypes={activeTypes}
          onToggleType={toggleType}
          query={query}
          onQuery={setQuery}
          visaOnly={visaOnly}
          onVisaOnly={setVisaOnly}
          minTrust={minTrust}
          onMinTrust={setMinTrust}
        />

        <main>
          <div className="feature-toggle-row" style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <button
              className={`btn ${activeTool === 'visa' ? 'primary' : ''}`}
              onClick={() => setActiveTool(activeTool === 'visa' ? null : 'visa')}
            >
              Visa hour check {selectedIds.length > 0 && `(${selectedIds.length} selected)`}
            </button>
            <button
              className={`btn ${activeTool === 'commute' ? 'primary' : ''}`}
              onClick={() => setActiveTool(activeTool === 'commute' ? null : 'commute')}
            >
              Commute check {selectedIds.length > 0 && `(${selectedIds.length} selected)`}
            </button>
            {selectedIds.length > 0 && (
              <button className="btn" onClick={() => setSelectedIds([])}>Clear selection</button>
            )}
          </div>

          {activeTool === 'visa' && (
            <VisaCheckBar selectedJobs={selectedJobs} />
          )}
          {activeTool === 'commute' && (
            <CommuteBar selectedJobs={selectedJobs} />
          )}

          <div className="results-bar">
            <span>{loading ? 'Searching…' : `${total} listing${total === 1 ? '' : 's'}`}</span>
            <select className="sort-select" value={sort} onChange={e => setSort(e.target.value)}>
              <option value="posted_date">Newest first</option>
              <option value="pay_min">Highest pay first</option>
              <option value="trust_score">Most trusted first</option>
            </select>
          </div>

          <JobList
            jobs={jobs}
            loading={loading}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelected}
          />
        </main>
      </div>
    </div>
  )
}

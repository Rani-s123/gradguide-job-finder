export default function Filters({
  jobTypes, activeTypes, onToggleType,
  query, onQuery,
  visaOnly, onVisaOnly,
  minTrust, onMinTrust,
}) {
  return (
    <aside className="filters">
      <h2>Filter jobs</h2>

      <div className="filter-group">
        <label className="group-label">Keyword</label>
        <input
          className="search-input"
          placeholder="e.g. barista, tutor, data entry"
          value={query}
          onChange={e => onQuery(e.target.value)}
        />
      </div>

      <div className="filter-group">
        <label className="group-label">Job type</label>
        <div className="chip-row">
          {jobTypes.map(t => (
            <button
              key={t}
              className={`chip ${activeTypes.includes(t) ? 'active' : ''}`}
              onClick={() => onToggleType(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <label className="group-label">Visa &amp; trust</label>
        <div className="checkbox-row" style={{ marginBottom: 10 }}>
          <input
            type="checkbox"
            id="visa-only"
            checked={visaOnly}
            onChange={e => onVisaOnly(e.target.checked)}
          />
          <label htmlFor="visa-only">On-campus / visa-friendly only</label>
        </div>
        <label className="group-label">Minimum trust score: {minTrust || 'any'}</label>
        <input
          type="range"
          min="0"
          max="90"
          step="10"
          value={minTrust}
          onChange={e => onMinTrust(Number(e.target.value))}
          style={{ width: '100%' }}
        />
      </div>
    </aside>
  )
}

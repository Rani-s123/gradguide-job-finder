import { useState } from 'react'

function trustTier(score) {
  if (score == null) return null
  if (score >= 75) return 'high'
  if (score >= 55) return 'medium'
  return 'low'
}

const FLAG_LABELS = {
  known_employer: { text: 'Recognized employer', good: true },
  employer_unverified: { text: 'Employer not on our known list', good: false },
  scam_keyword_match: { text: 'Contains common scam wording', good: false },
  vague_location: { text: 'Vague or missing location', good: false },
  no_parsable_pay: { text: 'Pay not clearly stated', good: false },
  pay_below_plausible_minimum: { text: 'Pay unusually low', good: false },
  no_description: { text: 'No job description given', good: false },
}

function TrustDetail({ flags }) {
  if (!flags) return null
  const list = flags.split(',').filter(Boolean)
  if (list.length === 0) return null
  return (
    <div className="trust-detail">
      {list.map(f => {
        const meta = FLAG_LABELS[f] || { text: f, good: false }
        return (
          <span key={f} className={`flag ${meta.good ? 'good' : 'bad'}`}>
            {meta.good ? '✓' : '·'} {meta.text}
          </span>
        )
      })}
    </div>
  )
}

function formatPay(job) {
  if (job.pay_min == null) return job.pay_raw || '—'
  const period = job.pay_period === 'year' ? '/yr' : job.pay_period === 'hour' ? '/hr' : ''
  const val = job.pay_min === job.pay_max
    ? `$${job.pay_min.toLocaleString()}`
    : `$${job.pay_min.toLocaleString()}–${job.pay_max.toLocaleString()}`
  return `${val}${period}`
}

function timeAgo(dateStr) {
  if (!dateStr) return 'date unknown'
  const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 14) return `${days}d ago`
  return dateStr
}

const SOURCE_LABELS = {
  campus_board: 'Campus board',
  cafe_chain: 'Bean & Leaf careers',
  city_board: 'City job board',
}

export default function JobList({ jobs, loading, selectedIds, onToggleSelect }) {
  const [expandedTrust, setExpandedTrust] = useState(null)

  if (loading && jobs.length === 0) {
    return (
      <div className="job-list">
        {[0, 1, 2, 3].map(i => <div key={i} className="skeleton-card" />)}
      </div>
    )
  }

  if (!loading && jobs.length === 0) {
    return (
      <div className="empty-state">
        <h3 style={{ marginBottom: 6 }}>No listings match those filters</h3>
        <p>Try widening the job type or lowering the trust score threshold.</p>
      </div>
    )
  }

  return (
    <div className="job-list">
      {jobs.map(job => {
        const tier = trustTier(job.trust_score)
        const selected = selectedIds.includes(job.listing_id)
        return (
          <article
            key={job.listing_id}
            className={`job-card type-${job.job_type}`}
            style={selected ? { outline: '2px solid #B8863A', outlineOffset: '-1px' } : undefined}
          >
            <div>
              <h3>{job.title}</h3>
              <div className="job-meta-line">
                {job.employer}<span className="sep">·</span>{job.location}
                <span className="sep">·</span>{timeAgo(job.posted_date)}
                <span className="sep">·</span>{SOURCE_LABELS[job.source_site] || job.source_site}
              </div>
              {job.description && <p className="job-desc">{job.description}</p>}
              <div className="job-tags">
                <span className="tag job-type">{job.job_type}</span>
                {job.visa_friendly_hint && <span className="tag visa-ok">Visa-friendly</span>}
              </div>
            </div>

            <div className="job-side">
              <div className="pay">
                {formatPay(job)}
                {job.pay_period === 'hour' && <span className="period"> /hr</span>}
              </div>
              {tier && (
                <button
                  className={`trust-badge ${tier}`}
                  onClick={() => setExpandedTrust(expandedTrust === job.listing_id ? null : job.listing_id)}
                  aria-expanded={expandedTrust === job.listing_id}
                >
                  Trust {job.trust_score}/100
                </button>
              )}
              {expandedTrust === job.listing_id && <TrustDetail flags={job.trust_flags} />}
              <div className="card-actions">
                <button className="btn" onClick={() => onToggleSelect(job.listing_id)}>
                  {selected ? 'Remove' : 'Select'}
                </button>
                <a className="btn primary" href={job.source_url} target="_blank" rel="noreferrer">
                  View
                </a>
              </div>
            </div>
          </article>
        )
      })}
    </div>
  )
}

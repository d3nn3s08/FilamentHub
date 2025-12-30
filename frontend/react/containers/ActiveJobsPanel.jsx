import React, { useEffect, useState } from 'react';
import PrintProgressCard from '../components/PrintProgressCard';

export default function ActiveJobsPanel() {
  const [jobs, setJobs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function fetchActive() {
      try {
        setLoading(true);
        const res = await fetch('/api/jobs/active');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (mounted) setJobs(Array.isArray(data) ? data : []);
      } catch (err) {
        if (mounted) setError(err.message || 'Fehler');
      } finally {
        if (mounted) setLoading(false);
      }
    }
    fetchActive();
    return () => { mounted = false; };
  }, []); // einmaliger Fetch, kein Polling

  if (loading) return (
    <section className="ph-panel ph-active-jobs">
      <h3>Aktive Drucke</h3>
      <p className="ph-dim">Lade…</p>
    </section>
  );

  if (error) return (
    <section className="ph-panel ph-active-jobs">
      <h3>Aktive Drucke</h3>
      <p className="ph-error">Fehler: {error}</p>
    </section>
  );

  if (!jobs || jobs.length === 0) return (
    <section className="ph-panel ph-active-jobs">
      <h3>Aktive Drucke</h3>
      <p className="ph-dim">Keine aktiven Drucke</p>
    </section>
  );

  return (
    <section className="ph-panel ph-active-jobs">
      <h3>Aktive Drucke</h3>
      <div className="ph-stack">
        {jobs.map(job => (
          <PrintProgressCard key={job.id} job={job} />
        ))}
      </div>
    </section>
  );
}

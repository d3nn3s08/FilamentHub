import React from 'react';
import PropTypes from 'prop-types';

// Präsentationskomponente für einen einzelnen aktiven Job
// Props: job: { id, name, printer_name, progress (number|null), eta_seconds (int|null), started_at }
export default function PrintProgressCard({ job }) {
  const { name, printer_name, progress, eta_seconds, started_at } = job || {};

  const started = started_at ? new Date(started_at) : null;
  const startedLabel = started ? started.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) : '-';

  const etaLabel = eta_seconds != null ? formatEta(eta_seconds) : '–';
  const progressValue = progress != null ? Math.round(progress) : null;

  return (
    <div className="ph-card ph-print-progress">
      <div className="ph-card-body">
        <div className="ph-row">
          <div className="ph-col">
            <div className="ph-job-name" title={name}>{name || 'Unbenannter Druck'}</div>
            <div className="ph-job-meta">{printer_name || 'Unbekannter Drucker'} · Start: {startedLabel}</div>
          </div>
          <div className="ph-col ph-col-right">
            <div className="ph-progress-value" aria-hidden>{progressValue != null ? `${progressValue}%` : '—'}</div>
            <div className="ph-progress-sub">ETA: {etaLabel}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatEta(seconds) {
  if (seconds <= 0) return '0s';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

PrintProgressCard.propTypes = {
  job: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    printer_name: PropTypes.string,
    progress: PropTypes.number,
    eta_seconds: PropTypes.number,
    started_at: PropTypes.string,
  }),
};

import React from "react";
import type { MonitoringReport } from "./monitoring";
import { sourceTrafficLight } from "./operational";

/** Each segment counts monitoring sources, never infrastructure health. */
export function SourcePostureChart({ report }: { report: MonitoringReport | null }) {
  const segments = sourceTrafficLight(report);
  const total = segments.reduce((sum, segment) => sum + segment.count, 0);
  let offset = 0;
  return <figure className="source-posture-chart" aria-label="PE and PC source alert posture distribution">
    <figcaption>Source alert posture</figcaption>
    <svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <circle className="posture-track" cx="60" cy="60" r="44" fill="none" strokeWidth="13" />
      {segments.map(segment => {
        const percentage = total ? segment.count / total * 100 : 0;
        const start = offset;
        offset += percentage;
        return segment.count ? <circle key={segment.key} className={`posture-segment posture-${segment.key}`} cx="60" cy="60" r="44" fill="none" strokeWidth="13" pathLength="100" strokeDasharray={`${percentage} ${100 - percentage}`} strokeDashoffset={-start} transform="rotate(-90 60 60)" /> : null;
      })}
      <text x="60" y="58" textAnchor="middle" className="posture-total">{total}</text>
      <text x="60" y="75" textAnchor="middle" className="posture-unit">sources</text>
    </svg>
    <ul>{segments.map(segment => <li key={segment.key}><span className={`posture-dot posture-${segment.key}`} aria-hidden="true" /><span>{segment.label}</span><strong>{segment.count}</strong></li>)}</ul>
    <p>PE and PC sources, not incident counts. Green means no critical/warning alerts in fresh evidence; it does not establish cluster health or completed recovery.</p>
  </figure>;
}

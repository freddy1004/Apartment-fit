"use client";
import { useState } from "react";
import { api } from "../lib/api";

export default function AmbiguityHelper() {
  const [text, setText] = useState("I want somewhere safe, quiet, and walkable near work");
  const [flags, setFlags] = useState<{ term: string; reason: string; suggestions: any[] }[]>([]);
  const [checked, setChecked] = useState(false);

  return (
    <div className="card">
      <div className="section-title">Criteria builder — describe what you want</div>
      <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} />
      <button className="primary" style={{ marginTop: 6 }}
        onClick={async () => { setFlags((await api.flagAmbiguities(text)).flags); setChecked(true); }}>
        Check for vague terms
      </button>
      {checked && flags.length === 0 && (
        <p className="explain pass" style={{ marginTop: 8 }}>No vague terms detected — these preferences look measurable.</p>
      )}
      {flags.map((f) => (
        <div className="flag" key={f.term}>
          <strong>“{f.term}” is ambiguous.</strong>
          <div className="muted" style={{ fontSize: 12 }}>{f.reason}</div>
          <ul style={{ margin: "6px 0 0 16px", fontSize: 12 }}>
            {f.suggestions.map((s, i) => <li key={i}>{s.label}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}

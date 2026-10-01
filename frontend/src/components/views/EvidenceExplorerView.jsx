import React from 'react';
import { EvidencePanel } from '../EvidencePanel.jsx';
import { EvidenceDecisionTrace } from '../visualization/EvidenceDecisionTrace.jsx';

export function EvidenceExplorerView({ data, selectedEvidenceId, onSelectEvidence }) {
  const evidenceList = data?.evidence || [];
  const toolCalls = data?.tool_calls || [];
  const claims = data?.claims || [];
  const criteria = data?.analysis?.criteria_evaluated || [];
  const recommendation = data?.analysis?.recommendation || null;

  return (
    <div className="view-container evidence-explorer-view">
      <div className="view-header">
        <div>
          <h2>Evidence Explorer & Provenance Trace</h2>
          <p className="view-subtitle">
            3-Tier evidence taxonomy (FACT, DERIVED_FACT, INFERENCE) with SHA-256 SQL provenance hashes.
          </p>
        </div>
      </div>

      {data ? (
        <div className="evidence-views-flow" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* End-to-End Visual Trace */}
          <EvidenceDecisionTrace
            evidence={evidenceList}
            claims={claims}
            criteria={criteria}
            recommendation={recommendation}
            onSelectEvidence={onSelectEvidence}
          />

          {/* Full Evidence & Provenance Panel */}
          <EvidencePanel
            evidence={evidenceList}
            toolCalls={toolCalls}
            claims={claims}
            criteria={criteria}
            recommendation={recommendation}
            selectedEvidenceId={selectedEvidenceId}
            onSelectEvidence={onSelectEvidence}
          />
        </div>
      ) : (
        <div className="card empty-card" role="status">
          <p className="no-data-text">No active investigation loaded. Run an investigation to inspect evidence lineage.</p>
        </div>
      )}
    </div>
  );
}

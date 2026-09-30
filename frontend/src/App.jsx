import React, { useState, useEffect } from 'react';
import { askQuestion } from './api/client.js';
import { QuestionInput } from './components/QuestionInput.jsx';
import { ExecutiveSummary } from './components/ExecutiveSummary.jsx';
import { AnswerCard } from './components/AnswerCard.jsx';
import { EvidencePanel } from './components/EvidencePanel.jsx';
import { DecisionCard } from './components/DecisionCard.jsx';
import { RobustnessCard } from './components/RobustnessCard.jsx';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [useMock, setUseMock] = useState(true);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);

  // Load initial mock investigation on mount
  useEffect(() => {
    handleRunInvestigation("What is our gross revenue by region?", true);
  }, []);

  const handleRunInvestigation = async (question, forceMock = useMock) => {
    setSelectedEvidenceId(null);
    setLoading(true);
    setError(null);

    try {
      const res = await askQuestion(question, 3, forceMock);
      if (res.error) {
        setError(res.error);
        setData(res);
      } else {
        setData(res);
      }
    } catch (err) {
      setError(err.message || "Failed to execute investigation request.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <header className="header">
        <h1 className="title">VERIDEX</h1>
        <p className="subtitle">Evidence-First AI Decision Intelligence Engine</p>
        <div className="header-badges">
          <span className="badge">AI Build Challenge 2026</span>
          <span className={`mode-badge ${useMock ? 'mock' : 'live'}`}>
            {useMock ? 'Mock API Mode' : 'Live API Mode'}
          </span>
        </div>
      </header>

      <main className="content">
        <QuestionInput
          onSubmit={(q) => handleRunInvestigation(q, useMock)}
          loading={loading}
          useMock={useMock}
          onToggleMock={(val) => {
            setUseMock(val);
            handleRunInvestigation(data?.question || "What is our gross revenue by region?", val);
          }}
        />

        {error && (
          <div className="card error-card">
            <h2>Investigation Warning / Error</h2>
            <p className="error-text">{error}</p>
          </div>
        )}

        {loading && (
          <div className="card loading-card">
            <div className="spinner"></div>
            <p>Executing safe read-only SQL query & assembling deterministic evidence...</p>
          </div>
        )}

        {data && !loading && (
          <>
            {/* Executive Summary & Key KPIs */}
            <ExecutiveSummary data={data} onSelectEvidence={setSelectedEvidenceId} />

            {/* 1. Synthesized Finding & Categorized Claims */}
            <AnswerCard
              answer={data.answer}
              claims={data.claims || []}
              selectedEvidenceId={selectedEvidenceId}
              onSelectEvidence={setSelectedEvidenceId}
            />

            {/* 2. Actionable Decision Recommendation */}
            {data.analysis && (
              <DecisionCard
                analysis={data.analysis}
                selectedEvidenceId={selectedEvidenceId}
                onSelectEvidence={setSelectedEvidenceId}
              />
            )}

            {/* 3. Robustness Assessment */}
            {data.analysis?.robustness && (
              <RobustnessCard
                robustness={data.analysis.robustness}
                selectedEvidenceId={selectedEvidenceId}
                onSelectEvidence={setSelectedEvidenceId}
              />
            )}

            {/* 4. Verified Evidence & SQL Provenance Panel */}
            <EvidencePanel
              evidence={data.evidence || []}
              toolCalls={data.tool_calls || []}
              selectedEvidenceId={selectedEvidenceId}
              onSelectEvidence={setSelectedEvidenceId}
            />
          </>
        )}
      </main>

      <footer className="footer">
        <p>VERIDEX — Traceable Evidence • Deterministic Calculations • Human Decisions</p>
      </footer>
    </div>
  );
}

export default App;

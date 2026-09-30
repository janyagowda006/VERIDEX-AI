import React, { useState, useEffect } from 'react';
import { askQuestion } from './api/client.js';
import { ThemeToggle } from './components/ThemeToggle.jsx';
import { QuestionInput } from './components/QuestionInput.jsx';
import { ExecutiveSummary } from './components/ExecutiveSummary.jsx';
import { AnswerCard } from './components/AnswerCard.jsx';
import { EvidencePanel } from './components/EvidencePanel.jsx';
import { DecisionCard } from './components/DecisionCard.jsx';
import { RobustnessCard } from './components/RobustnessCard.jsx';
import { HumanReviewPanel } from './components/HumanReviewPanel.jsx';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [useMock, setUseMock] = useState(true);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);

  // Theme state: respects localStorage preference, fallback to system preference
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('veridex_theme');
      if (saved === 'dark' || saved === 'light') return saved;
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      }
    } catch {
      // safe fallback for restricted sandbox environments
    }
    return 'light';
  });

  useEffect(() => {
    try {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('veridex_theme', theme);
    } catch {
      // safe fallback
    }
  }, [theme]);

  const handleToggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

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
      <header className="header" role="banner">
        <div className="header-top">
          <div className="brand-group">
            <div className="brand-logo" aria-hidden="true">
              <span className="logo-symbol">V</span>
            </div>
            <div>
              <h1 className="title">VERIDEX</h1>
              <p className="subtitle">Evidence-First AI Decision Intelligence Engine</p>
            </div>
          </div>
          <div className="header-controls">
            <div className="header-badges">
              <span className="badge badge-platform">AI Build Challenge 2026</span>
              <span className={`mode-badge ${useMock ? 'mock' : 'live'}`}>
                <span className="mode-dot" aria-hidden="true">●</span>
                {useMock ? 'Mock API Mode' : 'Live API Mode'}
              </span>
            </div>
            <ThemeToggle theme={theme} onToggle={handleToggleTheme} />
          </div>
        </div>
      </header>

      <main className="content" role="main">
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
          <div className="card error-card" role="alert" aria-live="assertive">
            <div className="error-icon" aria-hidden="true">⚠️</div>
            <div className="error-body">
              <h2>Investigation Notice</h2>
              <p className="error-text">{error}</p>
            </div>
          </div>
        )}

        {loading && (
          <div className="card loading-card" role="status" aria-live="polite">
            <div className="spinner" aria-hidden="true"></div>
            <div className="loading-content">
              <h3>Executing Investigation Pipeline</h3>
              <p>Executing safe read-only SQL queries, evaluating deterministic calculations, and assembling evidence...</p>
            </div>
          </div>
        )}

        {data && !loading && (
          <div className="investigation-flow">
            {/* Executive Summary & Key KPIs */}
            <ExecutiveSummary data={data} onSelectEvidence={setSelectedEvidenceId} />

            {/* 1. Synthesized Finding & Categorized Claims */}
            <section className="investigation-step" aria-label="Step 1: Synthesized Finding and Claims">
              <AnswerCard
                answer={data.answer}
                claims={data.claims || []}
                selectedEvidenceId={selectedEvidenceId}
                onSelectEvidence={setSelectedEvidenceId}
              />
            </section>

            {/* 2. Evidence & SQL Provenance Trace */}
            <section className="investigation-step" aria-label="Step 2: Evidence and Provenance Trace">
              <EvidencePanel
                evidence={data.evidence || []}
                toolCalls={data.tool_calls || []}
                selectedEvidenceId={selectedEvidenceId}
                onSelectEvidence={setSelectedEvidenceId}
              />
            </section>

            {/* 3. Actionable Decision Recommendation */}
            {data.analysis && (
              <section className="investigation-step" aria-label="Step 3: Actionable Decision Recommendation">
                <DecisionCard
                  analysis={data.analysis}
                  selectedEvidenceId={selectedEvidenceId}
                  onSelectEvidence={setSelectedEvidenceId}
                />
              </section>
            )}

            {/* 4. Human-in-the-Loop Audit & Review */}
            <section className="investigation-step" aria-label="Step 4: Human-in-the-Loop Audit & Review">
              <HumanReviewPanel
                key={data?.metadata?.investigation_id || "inv_mock_123456"}
                investigationId={data?.metadata?.investigation_id || "inv_mock_123456"}
                investigationStatus={
                  data?.status || (
                    data?.metadata?.robustness_status === 'SENSITIVE' || data?.analysis?.robustness?.status === 'SENSITIVE'
                      ? 'REQUIRES_REVIEW'
                      : 'COMPLETED'
                  )
                }
                latestReview={data?.latest_review || null}
                reviewCount={data?.review_count || 0}
                useMock={useMock}
              />
            </section>

            {/* 5. Robustness Assessment */}
            {data.analysis?.robustness && (
              <section className="investigation-step" aria-label="Step 5: Robustness Assessment">
                <RobustnessCard
                  key={data?.metadata?.investigation_id || "inv_mock_123456"}
                  robustness={data.analysis.robustness}
                  investigationId={data?.metadata?.investigation_id || "inv_mock_123456"}
                  selectedEvidenceId={selectedEvidenceId}
                  onSelectEvidence={setSelectedEvidenceId}
                  useMock={useMock}
                />
              </section>
            )}
          </div>
        )}
      </main>

      <footer className="footer" role="contentinfo">
        <p>VERIDEX — Traceable Evidence • Deterministic Calculations • Human Decisions</p>
      </footer>
    </div>
  );
}

export default App;

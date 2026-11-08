import React, { useState, useEffect, useCallback } from 'react';
import { askQuestion, getInvestigationDetail } from './api/client.js';
import { AuthProvider } from './context/AuthContext.jsx';
import { useAuth } from './context/useAuth.js';
import { LoginModal } from './components/LoginModal.jsx';
import { Sidebar } from './components/Sidebar.jsx';
import { ThemeToggle } from './components/ThemeToggle.jsx';
import { InvestigationHistoryDrawer } from './components/InvestigationHistoryDrawer.jsx';
import { GlobalAnalyticsPanel } from './components/GlobalAnalyticsPanel.jsx';
import { OverviewView } from './components/views/OverviewView.jsx';
import { InvestigationWorkspaceView } from './components/views/InvestigationWorkspaceView.jsx';
import { DecisionView } from './components/views/DecisionView.jsx';
import { RobustnessView } from './components/views/RobustnessView.jsx';
import { EvidenceExplorerView } from './components/views/EvidenceExplorerView.jsx';
import { InvestigationDetailView } from './components/views/InvestigationDetailView.jsx';
import { HistoryView } from './components/views/HistoryView.jsx';
import { SourcesView } from './components/views/SourcesView.jsx';
import './App.css';

function AppWorkspace() {
  const { currentUser, isAuthenticated, isLoading: authLoading, login, logout, authError } = useAuth();

  const [activeView, setActiveView] = useState('overview');
  const [data, setData] = useState(null);
  const [activeInvestigationId, setActiveInvestigationId] = useState(null);
  const [turns, setTurns] = useState([]);
  const [activeTurnNumber, setActiveTurnNumber] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Live vs Mock mode: Live by default!
  const [useMock, setUseMock] = useState(false);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isAnalyticsOpen, setIsAnalyticsOpen] = useState(false);

  // Theme state: respects localStorage preference, fallback to system preference
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('veridex_theme');
      if (saved === 'dark' || saved === 'light') return saved;
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      }
    } catch {
      // safe fallback
    }
    return 'dark';
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

  const handleStartNewInvestigation = () => {
    setActiveInvestigationId(null);
    setTurns([]);
    setActiveTurnNumber(1);
    setData(null);
    setError(null);
    setSelectedEvidenceId(null);
    setActiveView('investigations');
  };

  const handleRunInvestigation = useCallback(async (question, forceMock = useMock, isNewInvestigation = false) => {
    setSelectedEvidenceId(null);
    setLoading(true);
    setError(null);

    const invIdToSend = isNewInvestigation ? null : activeInvestigationId;

    try {
      const res = await askQuestion(question, 3, forceMock, invIdToSend);
      if (res.error) {
        setError(res.error);
      }

      const targetInvId = res.investigation_id || res.metadata?.investigation_id || invIdToSend || "inv_active";
      const isContinuation = Boolean(!isNewInvestigation && invIdToSend && targetInvId === invIdToSend);
      const nextTurnNum = isContinuation ? turns.length + 1 : 1;

      const newTurnItem = {
        turn_id: `turn_${targetInvId}_${nextTurnNum}`,
        investigation_id: targetInvId,
        turn_number: nextTurnNum,
        question: res.question || question,
        answer: res.answer || "Investigation analysis completed.",
        evidence_count: res.evidence ? res.evidence.length : (res.metadata?.total_evidence_items || 0),
        tool_calls_count: res.tool_calls ? res.tool_calls.length : 1,
        execution_time_ms: res.tool_calls?.[0]?.result?.metadata?.execution_time_ms || 14.2,
        created_at: new Date().toISOString(),
        result_payload: res
      };

      if (nextTurnNum === 1) {
        setTurns([newTurnItem]);
      } else {
        setTurns((prev) => [...prev, newTurnItem]);
      }

      setActiveInvestigationId(targetInvId);
      setActiveTurnNumber(nextTurnNum);
      setData(res);
      setActiveView('investigations');
    } catch (err) {
      setError(err.detail || err.message || "Failed to execute investigation request.");
    } finally {
      setLoading(false);
    }
  }, [activeInvestigationId, turns, useMock]);

  const handleSelectHistoricalInvestigation = async (invId) => {
    setSelectedEvidenceId(null);
    setLoading(true);
    setError(null);

    try {
      const detail = await getInvestigationDetail(invId, useMock);
      let parsedPayload = {};
      if (detail.result_json) {
        try {
          parsedPayload = typeof detail.result_json === 'string' ? JSON.parse(detail.result_json) : detail.result_json;
        } catch {
          // fallback
        }
      }

      const combinedData = {
        ...parsedPayload,
        question: detail.question || parsedPayload.question || "Historical Business Question",
        status: detail.status,
        latest_review: detail.latest_review,
        review_count: detail.review_count || 0,
        metadata: {
          ...(parsedPayload.metadata || {}),
          investigation_id: detail.investigation_id,
          robustness_status: detail.robustness_status || parsedPayload?.metadata?.robustness_status || "STABLE"
        }
      };

      const fetchedTurns = detail.turns || [];
      let turnItems = [];

      if (fetchedTurns.length > 0) {
        turnItems = fetchedTurns.map((t, idx) => ({
          turn_id: t.turn_id || `turn_${detail.investigation_id}_${t.turn_number}`,
          investigation_id: detail.investigation_id,
          turn_number: t.turn_number,
          question: t.question,
          answer: t.answer,
          evidence_count: t.evidence_count ?? 0,
          tool_calls_count: t.tool_calls_count ?? 1,
          execution_time_ms: t.execution_time_ms ?? 14.2,
          created_at: t.created_at || new Date().toISOString(),
          result_payload: idx === fetchedTurns.length - 1 ? combinedData : {
            question: t.question,
            answer: t.answer,
            claims: [],
            evidence: [],
            metadata: { investigation_id: detail.investigation_id, total_turns: t.turn_number }
          }
        }));
      } else {
        turnItems = [
          {
            turn_id: `turn_${detail.investigation_id}_1`,
            investigation_id: detail.investigation_id,
            turn_number: 1,
            question: detail.question || "Historical Business Question",
            answer: combinedData.answer || "Historical analysis summary",
            evidence_count: detail.evidence_count || (combinedData.evidence ? combinedData.evidence.length : 0),
            tool_calls_count: detail.tool_calls_count || 1,
            execution_time_ms: detail.execution_time_ms || 14.2,
            created_at: detail.created_at || new Date().toISOString(),
            result_payload: combinedData
          }
        ];
      }

      setTurns(turnItems);
      setActiveInvestigationId(detail.investigation_id);
      setActiveTurnNumber(turnItems[turnItems.length - 1].turn_number);
      setData(combinedData);
      setActiveView('detail');
    } catch (err) {
      setError(err.detail || err.message || "Failed to load historical investigation details.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTurn = (turnNum) => {
    const target = turns.find((t) => t.turn_number === turnNum);
    if (target) {
      setActiveTurnNumber(turnNum);
      if (target.result_payload) {
        setData(target.result_payload);
      }
    }
  };

  // View titles for header breadcrumbs
  const VIEW_TITLES = {
    overview: 'Overview',
    investigations: 'Investigations Workspace',
    sources: 'Data Sources & Schema',
    evidence: 'Evidence Explorer',
    decisions: 'Decision Intelligence',
    robustness: 'Robustness Analysis',
    detail: 'Investigation Audit Detail',
    history: 'Investigation History',
    settings: 'Security & Settings'
  };

  // If auth is loading on initial startup
  if (authLoading) {
    return (
      <div className="history-state-container" style={{ minHeight: '100vh' }}>
        <span className="btn-spinner" aria-hidden="true"></span>
        <span>Initializing VERIDEX Decision Intelligence Platform...</span>
      </div>
    );
  }

  // If user is not authenticated, show real Login Screen
  if (!isAuthenticated) {
    return (
      <LoginModal
        isOpen={true}
        onLogin={login}
        initialError={authError}
      />
    );
  }

  return (
    <div className="app-shell">
      {/* Persistent Left Sidebar Navigation */}
      <Sidebar
        activeView={activeView}
        onSelectView={setActiveView}
        currentUser={currentUser}
        workspaceName="Acme Retail"
        onLogout={logout}
      />

      {/* Main Viewport Container */}
      <div className="main-viewport">
        {/* Top Header Application Bar */}
        <header className="app-header" role="banner">
          <div className="header-left">
            <span className="header-breadcrumb">
              <span className="crumb-root">VERIDEX</span>
              <span className="crumb-sep">/</span>
              <span className="crumb-current">{VIEW_TITLES[activeView] || 'Workspace'}</span>
            </span>
            {activeInvestigationId && activeView === 'investigations' && (
              <span className="active-inv-tag" title="Active investigation identifier">
                {activeInvestigationId}
              </span>
            )}
          </div>

          <div className="header-controls">
            {activeInvestigationId && (
              <button
                type="button"
                className="btn-new-investigation-header"
                onClick={handleStartNewInvestigation}
                aria-label="Start a new investigation"
              >
                <span className="btn-icon" aria-hidden="true">+</span>
                New Thread
              </button>
            )}

            <button
              type="button"
              className="btn-analytics-toggle"
              onClick={() => setIsAnalyticsOpen(true)}
              aria-label="Open global analytics dashboard"
            >
              <span className="btn-icon" aria-hidden="true">📊</span>
              Analytics
            </button>

            <button
              type="button"
              className="btn-history-toggle"
              onClick={() => setIsHistoryOpen(true)}
              aria-label="Open investigation history drawer"
            >
              <span className="btn-icon" aria-hidden="true">📜</span>
              History
            </button>

            <div className="header-badges">
              <span className="badge badge-platform">AI Build Challenge 2026</span>
              <button
                type="button"
                className={`mode-badge ${useMock ? 'mock' : 'live'}`}
                onClick={() => setUseMock(!useMock)}
                title="Toggle between Live Backend Mode and Offline Mock Mode"
              >
                <span className="mode-dot" aria-hidden="true">●</span>
                {useMock ? 'Mock Mode' : 'Live API Mode'}
              </button>
            </div>

            {/* Authenticated User & Role Profile */}
            <div className="role-switcher-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="user-role-badge">
                👤 {currentUser?.full_name || currentUser?.email} (<strong>{currentUser?.role || 'ANALYST'}</strong>)
              </span>
              <button
                type="button"
                className="btn btn-outline btn-xs"
                onClick={logout}
                title="Sign out of active session"
              >
                Sign Out
              </button>
            </div>

            <ThemeToggle theme={theme} onToggle={handleToggleTheme} />
          </div>
        </header>

        {/* Dynamic Main Content View */}
        <main className="content" role="main">
          {/* VIEW: OVERVIEW */}
          {activeView === 'overview' && (
            <OverviewView
              currentUser={currentUser}
              activeData={data}
              onRunInvestigation={(q) => handleRunInvestigation(q, useMock, true)}
              onSelectInvestigation={handleSelectHistoricalInvestigation}
              onNavigate={setActiveView}
              useMock={useMock}
            />
          )}

          {/* VIEW: INVESTIGATIONS (Active Investigation Workspace) */}
          {activeView === 'investigations' && (
            <InvestigationWorkspaceView
              data={data}
              turns={turns}
              activeTurnNumber={activeTurnNumber}
              onSelectTurn={handleSelectTurn}
              activeInvestigationId={activeInvestigationId}
              onNewInvestigation={handleStartNewInvestigation}
              onRunInvestigation={handleRunInvestigation}
              loading={loading}
              error={error}
              useMock={useMock}
              onToggleMock={(val) => {
                setUseMock(val);
                if (data?.question) {
                  handleRunInvestigation(data.question, val, true);
                }
              }}
              selectedEvidenceId={selectedEvidenceId}
              onSelectEvidence={setSelectedEvidenceId}
              currentUser={currentUser}
              onNavigate={setActiveView}
            />
          )}

          {/* VIEW: DATA SOURCES & SCHEMA */}
          {activeView === 'sources' && (
            <SourcesView
              currentUser={currentUser}
              onNavigate={setActiveView}
            />
          )}

          {/* VIEW: EVIDENCE (Dedicated Evidence Explorer) */}
          {activeView === 'evidence' && (
            <EvidenceExplorerView
              evidence={data?.evidence || []}
              toolCalls={data?.tool_calls || []}
              claims={data?.claims || []}
              criteria={data?.analysis?.criteria_evaluated || []}
              recommendation={data?.analysis?.recommendation || null}
              selectedEvidenceId={selectedEvidenceId}
              onSelectEvidence={setSelectedEvidenceId}
              investigationId={activeInvestigationId || data?.metadata?.investigation_id || 'inv_active'}
              onNavigate={setActiveView}
            />
          )}

          {/* VIEW: DECISIONS (Dedicated Decision Intelligence) */}
          {activeView === 'decisions' && (
            <DecisionView
              data={data}
              selectedEvidenceId={selectedEvidenceId}
              onSelectEvidence={setSelectedEvidenceId}
              onNavigate={setActiveView}
              currentUser={currentUser}
              useMock={useMock}
            />
          )}

          {/* VIEW: ROBUSTNESS (Dedicated Robustness Analysis) */}
          {activeView === 'robustness' && (
            <RobustnessView
              data={data}
              onNavigate={setActiveView}
              currentUser={currentUser}
              useMock={useMock}
              onRobustnessUpdated={(reassessed) => {
                if (data) {
                  setData((prev) => ({
                    ...prev,
                    analysis: {
                      ...(prev?.analysis || {}),
                      robustness: reassessed.robustness
                    }
                  }));
                }
              }}
            />
          )}

          {/* VIEW: DETAIL (Dedicated Investigation Audit Detail) */}
          {activeView === 'detail' && (
            <InvestigationDetailView
              data={data}
              onNavigate={setActiveView}
              onSelectEvidence={setSelectedEvidenceId}
              currentUser={currentUser}
              useMock={useMock}
            />
          )}

          {/* VIEW: HISTORY (Real Investigation Audit History) */}
          {activeView === 'history' && (
            <HistoryView
              onSelectInvestigation={handleSelectHistoricalInvestigation}
              onNavigate={setActiveView}
              currentUser={currentUser}
              useMock={useMock}
            />
          )}

          {/* VIEW: SETTINGS */}
          {activeView === 'settings' && (
            <div className="view-shell settings-view-shell">
              <div className="card settings-card">
                <h2 className="section-heading">System & Security Settings</h2>
                <div className="settings-section">
                  <h3>Active User & Security Context</h3>
                  <div className="setting-row">
                    <span>Authenticated User:</span>
                    <strong>{currentUser?.full_name} ({currentUser?.email})</strong>
                  </div>
                  <div className="setting-row">
                    <span>Enterprise Role:</span>
                    <span className="badge badge-platform">{currentUser?.role}</span>
                  </div>
                  <div className="setting-row">
                    <span>User Identifier:</span>
                    <code>{currentUser?.user_id}</code>
                  </div>
                  <div className="setting-row" style={{ marginTop: '0.5rem' }}>
                    <button type="button" className="btn btn-outline btn-sm" onClick={logout}>
                      Sign Out of VERIDEX
                    </button>
                  </div>
                </div>

                <div className="settings-section" style={{ marginTop: '1.5rem' }}>
                  <h3>Security & Enforcement Guarantees</h3>
                  <div className="setting-row">
                    <span>Read-Only SQL Execution:</span>
                    <span className="status-badge status-badge-ok">✓ Enforced (SQLGlot AST validation)</span>
                  </div>
                  <div className="setting-row">
                    <span>Deterministic Calculations:</span>
                    <span className="status-badge status-badge-ok">✓ Enforced (Python numeric engine)</span>
                  </div>
                  <div className="setting-row">
                    <span>Evidence Lineage & Provenance:</span>
                    <span className="status-badge status-badge-ok">✓ Enforced (SHA-256 query hashing)</span>
                  </div>
                  <div className="setting-row">
                    <span>Self-Review Separation of Duties:</span>
                    <span className="status-badge status-badge-ok">✓ Enforced (Investigator cannot review own thread)</span>
                  </div>
                  <div className="setting-row">
                    <span>Multi-turn IDOR Guard:</span>
                    <span className="status-badge status-badge-ok">✓ Enforced (Thread ownership validation)</span>
                  </div>
                </div>

                <div className="settings-section" style={{ marginTop: '1.5rem' }}>
                  <h3>Appearance & Preferences</h3>
                  <div className="setting-row">
                    <span>Color Theme:</span>
                    <ThemeToggle theme={theme} onToggle={handleToggleTheme} />
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>

        {/* Footer */}
        <footer className="footer" role="contentinfo">
          <p>VERIDEX — Traceable Evidence • Deterministic Calculations • Human Decisions</p>
        </footer>

        {/* Slide-over Drawers */}
        <InvestigationHistoryDrawer
          isOpen={isHistoryOpen}
          onClose={() => setIsHistoryOpen(false)}
          onSelectInvestigation={handleSelectHistoricalInvestigation}
          useMock={useMock}
          currentUser={currentUser}
        />

        <GlobalAnalyticsPanel
          isOpen={isAnalyticsOpen}
          onClose={() => setIsAnalyticsOpen(false)}
          useMock={useMock}
        />
      </div>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <AppWorkspace />
    </AuthProvider>
  );
}

export default App;

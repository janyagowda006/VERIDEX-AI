import React, { useState, useEffect, useCallback } from 'react';
import { askQuestion, getInvestigationDetail, getMe } from './api/client.js';
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
import './App.css';

function App() {
  const [activeView, setActiveView] = useState('investigations');
  const [data, setData] = useState(null);
  const [activeInvestigationId, setActiveInvestigationId] = useState(null);
  const [turns, setTurns] = useState([]);
  const [activeTurnNumber, setActiveTurnNumber] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [useMock, setUseMock] = useState(true);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isAnalyticsOpen, setIsAnalyticsOpen] = useState(false);

  // Enterprise Auth & RBAC State
  const [userRole, setUserRole] = useState('ANALYST');
  const [currentUser, setCurrentUser] = useState({
    user_id: "usr_analyst_01",
    email: "analyst@veridex.internal",
    full_name: "Lead Analyst",
    role: "ANALYST",
    is_active: true
  });

  const handleSwitchRole = async (newRole) => {
    setUserRole(newRole);
    try {
      const u = await getMe(useMock, newRole);
      if (u) setCurrentUser(u);
    } catch {
      // fallback
    }
  };

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

      const targetInvId = res.investigation_id || res.metadata?.investigation_id || invIdToSend || "inv_mock_123456";
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
      setError(err.message || "Failed to execute investigation request.");
    } finally {
      setLoading(false);
    }
  }, [activeInvestigationId, turns, useMock]);

  // Load initial investigation on mount
  useEffect(() => {
    handleRunInvestigation("What is our gross revenue by region?", true, true);
  }, [handleRunInvestigation]);

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
      setActiveView('investigations');
    } catch (err) {
      setError(err.message || "Failed to load historical investigation details.");
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
    investigations: 'Investigations',
    sources: 'Data Sources',
    evidence: 'Evidence Explorer',
    decisions: 'Decision Intelligence',
    robustness: 'Robustness Analysis',
    detail: 'Investigation Audit',
    history: 'Investigation History',
    settings: 'Settings'
  };

  return (
    <div className="app-shell">
      {/* Persistent Left Sidebar Navigation */}
      <Sidebar
        activeView={activeView}
        onSelectView={setActiveView}
        currentUser={currentUser}
        workspaceName="Acme Retail"
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
              <span className={`mode-badge ${useMock ? 'mock' : 'live'}`}>
                <span className="mode-dot" aria-hidden="true">●</span>
                {useMock ? 'Mock API Mode' : 'Live API Mode'}
              </span>
            </div>

            {/* Dev Role Switcher */}
            <div className="role-switcher-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <select
                className="role-switcher-select"
                value={userRole}
                onChange={(e) => handleSwitchRole(e.target.value)}
                aria-label="Switch User Role for Dev Testing"
              >
                <option value="ANALYST">Role: ANALYST (Lead Analyst)</option>
                <option value="REVIEWER">Role: REVIEWER (Senior Reviewer)</option>
                <option value="AUDITOR">Role: AUDITOR (Compliance Auditor)</option>
                <option value="ADMIN">Role: ADMIN (System Admin)</option>
              </select>
              <span className="user-role-badge">
                👤 {currentUser?.full_name || userRole}
              </span>
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
                handleRunInvestigation(data?.question || "What is our gross revenue by region?", val, true);
              }}
              selectedEvidenceId={selectedEvidenceId}
              onSelectEvidence={setSelectedEvidenceId}
              currentUser={currentUser}
              onNavigate={setActiveView}
            />
          )}

          {/* VIEW: DATA SOURCES */}
          {activeView === 'sources' && (
            <div className="view-shell sources-view-shell">
              <div className="card safe-access-banner">
                <span className="safe-badge">RO</span>
                <div>
                  <strong>Read-only access guaranteed.</strong>
                  <span> VERIDEX runs safe read-only SQL queries. It never alters database state or inserts records.</span>
                </div>
              </div>
              <div className="card sources-table-card">
                <div className="card-header-row">
                  <h2 className="section-heading">Connected Data Sources</h2>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Source Name</th>
                      <th>Type</th>
                      <th>Access</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><strong>Operations Database</strong></td>
                      <td>SQL Database (PostgreSQL / SQLite)</td>
                      <td>Read-Only Safe Mode</td>
                      <td><span className="status-badge status-badge-ok">Connected</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* VIEW: EVIDENCE (Dedicated Prototype Evidence Explorer) */}
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

          {/* VIEW: DECISIONS (Dedicated Prototype Decision Intelligence) */}
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

          {/* VIEW: ROBUSTNESS (Dedicated Prototype Robustness Analysis) */}
          {activeView === 'robustness' && (
            <RobustnessView
              data={data}
              onNavigate={setActiveView}
              currentUser={currentUser}
              useMock={useMock}
            />
          )}

          {/* VIEW: DETAIL (Dedicated Prototype Investigation Audit Detail) */}
          {activeView === 'detail' && (
            <InvestigationDetailView
              data={data}
              onNavigate={setActiveView}
              onSelectEvidence={setSelectedEvidenceId}
              currentUser={currentUser}
              useMock={useMock}
            />
          )}

          {/* VIEW: HISTORY */}
          {activeView === 'history' && (
            <div className="view-shell history-view-shell">
              <div className="card placeholder-card">
                <div className="card-header-row">
                  <h2 className="section-heading">Investigation History</h2>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => setIsHistoryOpen(true)}
                  >
                    Open History Drawer 📜
                  </button>
                </div>
                <p>Browse past investigations, filter by review status or robustness classification, and review audit traces.</p>
                {turns.length > 0 && (
                  <div style={{ marginTop: '1rem' }}>
                    <h4>Current Session Investigations ({turns.length} Turn{turns.length > 1 ? 's' : ''})</h4>
                    <table className="data-table" style={{ marginTop: '0.5rem' }}>
                      <thead>
                        <tr>
                          <th>Turn</th>
                          <th>Question</th>
                          <th>Evidence</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {turns.map((t) => (
                          <tr key={t.turn_id}>
                            <td><strong>#{t.turn_number}</strong></td>
                            <td>{t.question}</td>
                            <td>{t.evidence_count} items</td>
                            <td>
                              <button
                                type="button"
                                className="btn btn-outline btn-sm"
                                onClick={() => {
                                  handleSelectTurn(t.turn_number);
                                  setActiveView('investigations');
                                }}
                              >
                                View
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* VIEW: SETTINGS */}
          {activeView === 'settings' && (
            <div className="view-shell settings-view-shell">
              <div className="card settings-card">
                <h2 className="section-heading">System & Security Settings</h2>
                <div className="settings-section">
                  <h3>Workspace Profile</h3>
                  <div className="setting-row">
                    <span>Workspace Name:</span>
                    <strong>Acme Retail</strong>
                  </div>
                  <div className="setting-row">
                    <span>Active User:</span>
                    <strong>{currentUser?.full_name || 'Gagandeep'} ({currentUser?.role || 'ANALYST'})</strong>
                  </div>
                </div>

                <div className="settings-section" style={{ marginTop: '1.5rem' }}>
                  <h3>Security & Enforcement</h3>
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
                    <span>Self-Review Protection:</span>
                    <span className="status-badge status-badge-ok">✓ Active (Creator cannot approve)</span>
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

        {/* Drawers */}
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

export default App;

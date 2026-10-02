import React, { useState, useEffect } from 'react';
import { askQuestion, getInvestigationDetail, getMe } from './api/client.js';
import { ThemeToggle } from './components/ThemeToggle.jsx';
import { QuestionInput } from './components/QuestionInput.jsx';
import { ConversationThread } from './components/ConversationThread.jsx';
import { ExecutiveSummary } from './components/ExecutiveSummary.jsx';
import { AnswerCard } from './components/AnswerCard.jsx';
import { EvidencePanel } from './components/EvidencePanel.jsx';
import { DecisionCard } from './components/DecisionCard.jsx';
import { RobustnessCard } from './components/RobustnessCard.jsx';
import { HumanReviewPanel } from './components/HumanReviewPanel.jsx';
import { InvestigationHistoryDrawer } from './components/InvestigationHistoryDrawer.jsx';
import { GlobalAnalyticsPanel } from './components/GlobalAnalyticsPanel.jsx';
import { Sidebar } from './components/Sidebar.jsx';
import { OverviewView } from './components/views/OverviewView.jsx';
import { DataSourcesView } from './components/views/DataSourcesView.jsx';
import { SettingsView } from './components/views/SettingsView.jsx';
import { HistoryView } from './components/views/HistoryView.jsx';
import { AuditTrailView } from './components/views/AuditTrailView.jsx';
import { EvidenceExplorerView } from './components/views/EvidenceExplorerView.jsx';
import { DecisionsView } from './components/views/DecisionsView.jsx';
import { LandingPage } from './components/views/LandingPage.jsx';
import { WorkspaceView } from './components/views/WorkspaceView.jsx';
import { InvestigationDetailView } from './components/views/InvestigationDetailView.jsx';
import { RobustnessView } from './components/views/RobustnessView.jsx';
import { EvidenceModelView } from './components/views/EvidenceModelView.jsx';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [activeInvestigationId, setActiveInvestigationId] = useState(null);
  const [turns, setTurns] = useState([]);
  const [activeTurnNumber, setActiveTurnNumber] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [useMock, setUseMock] = useState(false);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isAnalyticsOpen, setIsAnalyticsOpen] = useState(false);

  // Prototype Multi-View & Sidebar Navigation State
  const [activeView, setActiveView] = useState('landing');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

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

  const handleStartNewInvestigation = () => {
    setActiveInvestigationId(null);
    setTurns([]);
    setActiveTurnNumber(1);
    setData(null);
    setError(null);
    setSelectedEvidenceId(null);
    setActiveView('workspace');
  };

  const handleRunInvestigation = async (question, forceMock = useMock, isNewInvestigation = false) => {
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
    } catch (err) {
      setError(err.message || "Failed to execute investigation request.");
    } finally {
      setLoading(false);
    }
  };

  // Load initial mock investigation on mount
  useEffect(() => {
    handleRunInvestigation("What is our gross revenue by region?", true, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      setActiveView('workspace');
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

  if (activeView === 'landing') {
    return <LandingPage onNavigate={(view) => setActiveView(view)} />;
  }

  if (activeView === 'model') {
    return <EvidenceModelView onNavigate={(view) => setActiveView(view)} />;
  }

  return (
    <div className="container app-shell">
      <header className="header" role="banner">
        <div className="header-top">
          <div
            className="brand-group"
            onClick={() => setActiveView('landing')}
            style={{ cursor: 'pointer' }}
            title="Return to Landing Page"
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setActiveView('landing')}
          >
            <div className="brand-logo" aria-hidden="true">
              <span className="logo-symbol">V</span>
            </div>
            <div>
              <h1 className="title">VERIDEX</h1>
              <p className="subtitle">Evidence-First AI Decision Intelligence Engine</p>
            </div>
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
              History Drawer
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
                style={{
                  padding: '0.25rem 0.5rem',
                  fontSize: '0.8125rem',
                  borderRadius: '0.375rem',
                  border: '1px solid var(--border-medium)',
                  backgroundColor: 'var(--bg-card)',
                  color: 'var(--text-primary)',
                  fontWeight: '500'
                }}
                aria-label="Switch User Role for Dev Testing"
              >
                <option value="ANALYST">Role: ANALYST (Lead Analyst)</option>
                <option value="REVIEWER">Role: REVIEWER (Senior Reviewer)</option>
                <option value="AUDITOR">Role: AUDITOR (Compliance Auditor)</option>
                <option value="ADMIN">Role: ADMIN (System Admin)</option>
              </select>
              <span className="user-role-badge" style={{ fontSize: '0.75rem', fontWeight: '600', padding: '0.2rem 0.4rem', borderRadius: '0.25rem', backgroundColor: 'var(--bg-card-subtle)', color: 'var(--text-secondary)', border: '1px solid var(--border-light)' }}>
                👤 {currentUser?.full_name || userRole}
              </span>
            </div>
            <ThemeToggle theme={theme} onToggle={handleToggleTheme} />
          </div>
        </div>
      </header>

      {/* Main Layout Grid with Sidebar Navigation */}
      <div className="app-body-layout" style={{ display: 'flex', gap: '1.25rem', width: '100%', alignItems: 'flex-start' }}>
        <Sidebar
          activeView={activeView}
          setActiveView={setActiveView}
          collapsed={sidebarCollapsed}
          setCollapsed={setSidebarCollapsed}
          userRole={userRole}
        />

        <main className="content main-view-content" role="main" style={{ flex: 1, minWidth: 0 }}>
          {/* Active View Renderer */}
          {activeView === 'overview' && (
            <OverviewView
              useMock={useMock}
              currentUser={currentUser}
              onNavigate={setActiveView}
              onSelectInvestigation={handleSelectHistoricalInvestigation}
            />
          )}

          {(activeView === 'datasources' || activeView === 'sources') && (
            <DataSourcesView useMock={useMock} currentUser={currentUser} onNavigate={setActiveView} />
          )}

          {activeView === 'settings' && (
            <SettingsView
              theme={theme}
              onToggleTheme={handleToggleTheme}
              useMock={useMock}
              onToggleMock={setUseMock}
              userRole={userRole}
              onSwitchRole={handleSwitchRole}
              currentUser={currentUser}
              onNavigate={setActiveView}
            />
          )}

          {activeView === 'history' && (
            <HistoryView
              onSelectInvestigation={(invId) => {
                handleSelectHistoricalInvestigation(invId);
              }}
              onNavigate={setActiveView}
              useMock={useMock}
              currentUser={currentUser}
            />
          )}

          {activeView === 'audit' && (
            <AuditTrailView useMock={useMock} currentUser={currentUser} />
          )}

          {(activeView === 'evidence' || activeView === 'model') && (
            <EvidenceExplorerView
              data={data}
              useMock={useMock}
              currentUser={currentUser}
              onNavigate={setActiveView}
              onSelectInvestigation={handleSelectHistoricalInvestigation}
            />
          )}

          {(activeView === 'decisions' || activeView === 'decision') && (
            <DecisionsView
              data={data}
              useMock={useMock}
              currentUser={currentUser}
              onNavigate={setActiveView}
              onSelectInvestigation={handleSelectHistoricalInvestigation}
            />
          )}

          {activeView === 'detail' && (
            <InvestigationDetailView
              data={data}
              useMock={useMock}
              currentUser={currentUser}
              onNavigate={setActiveView}
            />
          )}

          {activeView === 'robustness' && (
            <RobustnessView
              data={data}
              useMock={useMock}
              currentUser={currentUser}
              onNavigate={setActiveView}
              onSelectInvestigation={handleSelectHistoricalInvestigation}
            />
          )}

          {(activeView === 'workspace' || activeView === 'ask') && (
            <WorkspaceView
              data={data}
              loading={loading}
              error={error}
              onRunInvestigation={handleRunInvestigation}
              activeInvestigationId={activeInvestigationId}
              currentUser={currentUser}
              useMock={useMock}
              turns={turns}
              activeTurnNumber={activeTurnNumber}
              onSelectTurn={handleSelectTurn}
              onNavigate={setActiveView}
            />
          )}
        </main>
      </div>

      <footer className="footer" role="contentinfo">
        <p>VERIDEX — Traceable Evidence • Deterministic Calculations • Human Decisions</p>
      </footer>

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
  );
}

export default App;

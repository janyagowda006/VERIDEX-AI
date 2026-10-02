import React, { useState } from 'react';
import './SettingsView.css';

export function SettingsView({ onNavigate }) {
  const [activeTab, setActiveTab] = useState('ws');
  const [workspaceName, setWorkspaceName] = useState('Acme Retail');
  const [savedNotice, setSavedNotice] = useState(false);

  // Preferences state
  const [density, setDensity] = useState('Comfortable');
  const [tech, setTech] = useState(false);
  const [panel, setPanel] = useState(true);

  const handleSaveWorkspace = () => {
    setSavedNotice(true);
    setTimeout(() => {
      setSavedNotice(false);
    }, 1600);
  };

  const handleCancelWorkspace = () => {
    setWorkspaceName('Acme Retail');
  };

  return (
    <main className="settings-page-container">
      <h1>Settings</h1>
      <div className="lay">
        <nav className="sn" id="sn">
          <a
            className={activeTab === 'ws' ? 'on' : ''}
            data-s="ws"
            onClick={() => setActiveTab('ws')}
          >
            Workspace
          </a>
          <a
            className={activeTab === 'model' ? 'on' : ''}
            data-s="model"
            onClick={() => setActiveTab('model')}
          >
            Model configuration
          </a>
          <a
            className={activeTab === 'src' ? 'on' : ''}
            data-s="src"
            onClick={() => setActiveTab('src')}
          >
            Data sources
          </a>
          <a
            className={activeTab === 'sec' ? 'on' : ''}
            data-s="sec"
            onClick={() => setActiveTab('sec')}
          >
            Security
          </a>
          <a
            className={activeTab === 'pref' ? 'on' : ''}
            data-s="pref"
            onClick={() => setActiveTab('pref')}
          >
            Preferences
          </a>
        </nav>

        <div className="sec" id="c">
          {activeTab === 'ws' && (
            <>
              <h2>Workspace</h2>
              <p>Basic details for this workspace.</p>
              <div className="card">
                <div className="row">
                  <div>
                    <b>Workspace name</b>
                    <small>Shown in the sidebar</small>
                  </div>
                  <input
                    className="inp"
                    value={workspaceName}
                    onChange={(e) => setWorkspaceName(e.target.value)}
                  />
                </div>
                <div className="row">
                  <div>
                    <b>Workspace ID</b>
                    <small>Read-only</small>
                  </div>
                  <div className="ro">ws_7f3a91c2</div>
                </div>
              </div>

              <div className="bar">
                <span className={`saved ${savedNotice ? 'show' : ''}`} id="sv">
                  Saved
                </span>
                <button className="btn" onClick={handleCancelWorkspace}>
                  Cancel
                </button>
                <button className="btn p" id="save" onClick={handleSaveWorkspace}>
                  Save changes
                </button>
              </div>
            </>
          )}

          {activeTab === 'model' && (
            <>
              <h2>Model configuration</h2>
              <p>How VERIDEX runs an investigation.</p>
              <div className="card">
                <div className="row">
                  <div>
                    <b>Model</b>
                    <small>Used for reasoning and answers</small>
                  </div>
                  <div className="ro">Configured on the server</div>
                </div>
              </div>
              <div className="info">
                These values come from the backend configuration. This page shows them but does not change them unless the backend exposes editable settings.
              </div>
            </>
          )}

          {activeTab === 'src' && (
            <>
              <h2>Data sources</h2>
              <p>Manage connected data in one place.</p>
              <div className="card">
                <div className="row">
                  <div>
                    <b>Connected sources</b>
                    <small>1 database, 1 CSV file, 1 Excel workbook</small>
                  </div>
                  <div style={{ justifySelf: 'end' }}>
                    <button
                      className="btn"
                      onClick={() => onNavigate && (onNavigate('sources') || onNavigate('datasources'))}
                    >
                      Open Data Sources →
                    </button>
                  </div>
                </div>
                <div className="row">
                  <div>
                    <b>Default source for new questions</b>
                    <small>Used when a question does not name a source</small>
                  </div>
                  <div className="ro">Operations database</div>
                </div>
              </div>
            </>
          )}

          {activeTab === 'sec' && (
            <>
              <h2>Security</h2>
              <p>What protects your data and answers today.</p>
              <div className="card">
                <div className="row">
                  <div>
                    <b>Read-only SQL</b>
                    <small>VERIDEX cannot modify your data</small>
                  </div>
                  <div>
                    <span className="tag ok" style={{ margin: 0 }}>
                      ✓ Enforced
                    </span>
                  </div>
                </div>
                <div className="row">
                  <div>
                    <b>Evidence tracing</b>
                    <small>Every claim links to its evidence</small>
                  </div>
                  <div>
                    <span className="tag ok" style={{ margin: 0 }}>
                      ✓ Enabled
                    </span>
                  </div>
                </div>
                <div className="row">
                  <div>
                    <b>Deterministic calculations</b>
                    <small>Totals, margins and rankings are computed by code</small>
                  </div>
                  <div>
                    <span className="tag ok" style={{ margin: 0 }}>
                      ✓ Enabled
                    </span>
                  </div>
                </div>
                <div className="row">
                  <div>
                    <b>Investigation limit</b>
                    <small>Maximum turns per question</small>
                  </div>
                  <div className="ro">5 turns</div>
                </div>
              </div>
            </>
          )}

          {activeTab === 'pref' && (
            <>
              <h2>Preferences</h2>
              <p>Personal display settings. Saved in this browser.</p>
              <div className="card">
                <div className="row">
                  <div>
                    <b>Theme</b>
                    <small>Appearance of the app</small>
                  </div>
                  <div className="seg">
                    <button className="on">Dark</button>
                    <button disabled title="Not available yet">
                      Light
                    </button>
                  </div>
                </div>
                <div className="row">
                  <div>
                    <b>Density</b>
                    <small>Spacing in tables and lists</small>
                  </div>
                  <div className="seg" id="dn">
                    <button
                      className={density === 'Comfortable' ? 'on' : ''}
                      onClick={() => setDensity('Comfortable')}
                    >
                      Comfortable
                    </button>
                    <button
                      className={density === 'Compact' ? 'on' : ''}
                      onClick={() => setDensity('Compact')}
                    >
                      Compact
                    </button>
                  </div>
                </div>
                <div className="row">
                  <div>
                    <b>Show technical details by default</b>
                    <small>Expand SQL and tool calls on investigation pages</small>
                  </div>
                  <button
                    className={`tg ${tech ? 'on' : ''}`}
                    aria-pressed={tech}
                    onClick={() => setTech(!tech)}
                  />
                </div>
                <div className="row">
                  <div>
                    <b>Open evidence panel automatically</b>
                    <small>Show evidence beside the answer on the Ask page</small>
                  </div>
                  <button
                    className={`tg ${panel ? 'on' : ''}`}
                    aria-pressed={panel}
                    onClick={() => setPanel(!panel)}
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      <p className="note">Sample values shown for illustration.</p>
    </main>
  );
}

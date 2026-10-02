import React, { useState, useRef } from 'react';
import './DataSourcesView.css';
import { uploadDataSource } from '../../api/client.js';

// Prototype data sources dataset matching P["sources"]
const PROTOTYPE_SOURCES = [
  {
    n: "Operations database",
    ic: "DB",
    ty: "SQL database",
    st: "Connected",
    c: "var(--ok, #4CB782)",
    sy: "12 min ago",
    ds: 5,
    desc: "Read-only connection · orders, regions, customers, products, returns",
    kv: [
      ["access", "read-only"],
      ["dialect", "SQL"],
      ["last_sync", "2026-09-30 14:00"],
      ["tables", "5"]
    ],
    T: {
      orders: {
        r: "18,420",
        c: [
          ["order_id", "integer"],
          ["region", "text"],
          ["quarter", "text"],
          ["revenue", "numeric"],
          ["profit", "numeric"],
          ["returned", "boolean"]
        ]
      },
      regions: {
        r: "4",
        c: [
          ["region", "text"],
          ["manager", "text"]
        ]
      },
      customers: {
        r: "3,912",
        c: [
          ["customer_id", "integer"],
          ["region", "text"],
          ["segment", "text"]
        ]
      },
      products: {
        r: "246",
        c: [
          ["product_id", "integer"],
          ["line", "text"],
          ["unit_cost", "numeric"]
        ]
      },
      returns: {
        r: "1,104",
        c: [
          ["order_id", "integer"],
          ["reason", "text"],
          ["date", "date"]
        ]
      }
    }
  },
  {
    n: "orders_2026.csv",
    ic: "CSV",
    ty: "CSV file",
    st: "Ready",
    c: "var(--ok, #4CB782)",
    sy: "Today, 09:20",
    ds: 1,
    desc: "Uploaded file · one dataset",
    kv: [
      ["size", "1.9 MB"],
      ["encoding", "UTF-8"],
      ["uploaded", "2026-09-30 09:20"]
    ],
    T: {
      orders_2026: {
        r: "18,420",
        c: [
          ["order_id", "integer"],
          ["region", "text"],
          ["quarter", "text"],
          ["revenue", "numeric"],
          ["profit", "numeric"]
        ]
      }
    }
  },
  {
    n: "regional_targets.xlsx",
    ic: "XLS",
    ty: "Excel workbook",
    st: "Stale",
    c: "var(--warn, #E0A94A)",
    sy: "Sep 24",
    ds: 3,
    desc: "Uploaded file · 3 sheets. Not refreshed in 6 days",
    kv: [
      ["size", "84 KB"],
      ["sheets", "3"],
      ["uploaded", "2026-09-24 11:05"]
    ],
    T: {
      targets: {
        r: "16",
        c: [
          ["region", "text"],
          ["quarter", "text"],
          ["target", "numeric"]
        ]
      },
      headcount: {
        r: "12",
        c: [
          ["region", "text"],
          ["fte", "integer"]
        ]
      },
      notes: {
        r: "9",
        c: [
          ["note", "text"]
        ]
      }
    }
  }
];

/**
 * VERIDEX Page 8: Data Sources View
 * Reconstructed with 100% exact visual and functional fidelity to veridex-prototype-v2.html P["sources"].
 */
export function DataSourcesView({
  useMock = false,
  currentUser: _currentUser,
  onNavigate: _onNavigate
}) {
  const [sourcesList, setSourcesList] = useState(PROTOTYPE_SOURCES);
  const [selectedSourceIndex, setSelectedSourceIndex] = useState(0);
  const [selectedTabIndex, setSelectedTabIndex] = useState(0);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [actionFeedback, setActionFeedback] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  const fileInputRef = useRef(null);

  const activeSource = sourcesList[selectedSourceIndex] || sourcesList[0];
  const datasetKeys = Object.keys(activeSource.T);
  const currentTabKey = datasetKeys[selectedTabIndex] || datasetKeys[0];
  const currentTable = activeSource.T[currentTabKey] || { r: "0", c: [] };

  const handleSelectSource = (index) => {
    setSelectedSourceIndex(index);
    setSelectedTabIndex(0);
  };

  const handleAction = () => {
    const actionName = activeSource.ic === 'DB' ? 'Refreshed schema' : 'File replaced';
    setActionFeedback(actionName);
    setTimeout(() => setActionFeedback(null), 2000);
  };

  const handleTriggerUpload = () => {
    setUploadError(null);
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      const res = await uploadDataSource(file, useMock);
      const isCsv = file.name.toLowerCase().endsWith('.csv');
      const newSource = {
        n: file.name,
        ic: isCsv ? 'CSV' : 'XLS',
        ty: isCsv ? 'CSV file' : 'Excel workbook',
        st: 'Ready',
        c: 'var(--ok, #4CB782)',
        sy: 'Just now',
        ds: 1,
        desc: `Uploaded dataset · table: ${res.table_name}`,
        kv: [
          ["table_name", res.table_name],
          ["rows_inserted", String(res.rows_inserted || 0)],
          ["columns", String(res.column_count || 0)],
          ["uploaded", "Just now"]
        ],
        T: {
          [res.table_name]: {
            r: String(res.rows_inserted || 0),
            c: (res.columns || []).map(col => [col, "text/numeric"])
          }
        }
      };

      setSourcesList(prev => [newSource, ...prev]);
      setSelectedSourceIndex(0);
      setSelectedTabIndex(0);
      setIsModalOpen(false);
      setActionFeedback("File uploaded successfully");
      setTimeout(() => setActionFeedback(null), 3000);
    } catch (err) {
      setUploadError(err.message || "Failed to upload file");
    } finally {
      setIsUploading(false);
      if (e.target) e.target.value = "";
    }
  };

  return (
    <div className="sources-page-container">
      {/* Hidden file input for uploading datasets */}
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={handleFileUpload}
        accept=".csv,.xlsx,.xls"
      />

      {/* Top Banner & Main Heading */}
      <div className="top">
        <div>
          <h1>Data sources</h1>
          <p className="sub">The business data VERIDEX can investigate.</p>
        </div>
        <button className="btn p" onClick={() => setIsModalOpen(true)}>
          + Add data source
        </button>
      </div>

      {/* Read-Only Safety Banner */}
      <div className="card safe">
        <span className="ic">RO</span>
        <span>
          <b>Read-only access.</b> VERIDEX runs safe read-only queries. It never changes your data.
        </span>
      </div>

      {/* 2-Column Main Layout */}
      <div className="cols">
        {/* Left Column: Connected Sources Table */}
        <div className="card">
          <div className="hd">
            <span className="cap">Connected sources · {sourcesList.length}</span>
          </div>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Last synced</th>
                  <th>Datasets</th>
                </tr>
              </thead>
              <tbody>
                {sourcesList.map((s, index) => (
                  <tr
                    key={`${s.n}-${index}`}
                    className={index === selectedSourceIndex ? 'on' : ''}
                    onClick={() => handleSelectSource(index)}
                  >
                    <td>
                      <div className="nm">
                        <span className="ic">{s.ic}</span>
                        {s.n}
                      </div>
                    </td>
                    <td className="m">{s.ty}</td>
                    <td>
                      <span className="st" style={{ '--c': s.c }}>
                        {s.st}
                      </span>
                    </td>
                    <td className="m">{s.sy}</td>
                    <td className="m">{s.ds}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Source Detail Panel */}
        <div className="card" id="dt">
          <div className="hd">
            <span className="cap">Source detail</span>
            <button className="btn" style={{ padding: '4px 10px' }} onClick={handleAction}>
              {actionFeedback || (activeSource.ic === 'DB' ? 'Refresh schema' : 'Replace file')}
            </button>
          </div>
          <div className="dt">
            <h3>{activeSource.n}</h3>
            <p>{activeSource.desc}</p>

            <div className="kv">
              {activeSource.kv.map((pair, idx) => (
                <React.Fragment key={idx}>
                  <span>{pair[0]}</span>
                  <span>{pair[1]}</span>
                </React.Fragment>
              ))}
            </div>

            <div className="cap" style={{ marginBottom: '8px' }}>
              {activeSource.ic === 'XLS' ? 'Sheets' : 'Datasets'} · {datasetKeys.length}
            </div>

            <div className="tabs">
              {datasetKeys.map((key, i) => (
                <button
                  key={key}
                  className={`tab ${i === selectedTabIndex ? 'on' : ''}`}
                  onClick={() => setSelectedTabIndex(i)}
                >
                  {key}
                </button>
              ))}
            </div>

            <table className="sch">
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {currentTable.c.map((col, idx) => (
                  <tr key={idx}>
                    <td>{col[0]}</td>
                    <td className="ty">{col[1]}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="rc">{currentTable.r} rows</div>
          </div>
        </div>
      </div>

      {/* Legend Footer */}
      <div className="lgd">
        <span className="st" style={{ '--c': 'var(--ok, #4CB782)' }}>
          Connected / ready
        </span>
        <span className="st" style={{ '--c': 'var(--warn, #E0A94A)' }}>
          Stale, not refreshed recently
        </span>
        <span className="st" style={{ '--c': '#D46A6A' }}>
          Error, needs attention
        </span>
      </div>

      {/* Footnote */}
      <p className="note">Sample data shown for illustration.</p>

      {/* Add Data Source Modal */}
      <div
        className={`sources-modal-overlay ${isModalOpen ? 'o' : ''}`}
        onClick={(e) => {
          if (e.target.classList.contains('sources-modal-overlay')) {
            setIsModalOpen(false);
          }
        }}
      >
        <div className="sources-modal">
          <h2>Add data source</h2>
          <p>Choose a source type. Select CSV or Excel to upload a custom dataset.</p>

          {uploadError && (
            <div style={{ color: '#d46a6a', background: 'rgba(212,106,106,0.1)', padding: '8px 12px', borderRadius: '4px', marginBottom: '12px', fontSize: '13px' }}>
              {uploadError}
            </div>
          )}

          <div className="ty2">
            <div style={{ opacity: 0.6, cursor: 'not-allowed' }}>
              <span className="ic">DB</span>
              <span>
                SQL database
                <small>Connect a relational database (Operations DB connected)</small>
              </span>
            </div>
            <div onClick={handleTriggerUpload} style={{ cursor: 'pointer' }}>
              <span className="ic">CSV</span>
              <span>
                CSV file {isUploading ? '(Uploading...)' : ''}
                <small>Upload a comma-separated file (.csv)</small>
              </span>
            </div>
            <div onClick={handleTriggerUpload} style={{ cursor: 'pointer' }}>
              <span className="ic">XLS</span>
              <span>
                Excel workbook {isUploading ? '(Uploading...)' : ''}
                <small>Upload an .xlsx / .xls file. Each sheet becomes a dataset</small>
              </span>
            </div>
          </div>

          <div className="ft">
            <button className="btn" onClick={() => setIsModalOpen(false)} disabled={isUploading}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

import './App.css'

function App() {
  return (
    <div className="container">
      <header className="header">
        <h1 className="title">VERIDEX</h1>
        <p className="subtitle">Evidence-First AI Decision Intelligence</p>
        <div className="badge">Phase 1 — Project Foundation</div>
      </header>

      <main className="content">
        <div className="card">
          <h2>Core Principle</h2>
          <p className="quote">"AI for reasoning, code for correctness."</p>
        </div>

        <div className="card status-card">
          <h2>System Status</h2>
          <ul className="status-list">
            <li><strong>Backend API:</strong> Ready (FastAPI GET /health)</li>
            <li><strong>Frontend:</strong> Ready (Vite + React)</li>
            <li><strong>Database:</strong> Configured (PostgreSQL Docker Compose)</li>
          </ul>
        </div>
      </main>

      <footer className="footer">
        <p>Build Fast with AI — AI Build Challenge 2026</p>
      </footer>
    </div>
  )
}

export default App

import { FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { createRoot } from "react-dom/client";
import {
  Activity, AlertCircle, BarChart3, Brain, CheckCircle2, CircleDollarSign, Clock3,
  Eye, FlaskConical, LayoutDashboard, LoaderCircle, Menu, Play, Plus, RefreshCw,
  Server, Settings, Timer, X, XCircle, Zap, CalendarDays, CheckSquare2, Target,
  ArrowUpRight, MoreHorizontal, Download, BookOpen, Workflow, Database, ShieldCheck
} from "lucide-react";
import "./styles.css";

type Run = { run_id: string; task_id?: string; status: string; attempts?: any[]; cost_usd?: number; total_tokens?: number; created_at?: string; error?: string };
type Task = { id: string; prompt: string; split?: string; category?: string };
const API_BASE = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "/api" : "")).replace(/\/$/, "");
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new Error("The API is not reachable. Start FastAPI on port 8000 or set VITE_API_URL to your deployed backend.");
  }
  if (!response.ok) throw new Error((await response.text()) || `Request failed (${response.status})`);
  return response.json();
}

const nav = [
  ["overview", "Overview", LayoutDashboard], ["runs", "Runs", Zap],
  ["experiments", "Experiments", FlaskConical], ["memory", "Memory", Brain],
  ["benchmarks", "Benchmarks", BarChart3], ["guide", "User guide", BookOpen], ["settings", "Settings", Settings],
] as const;

function durationFor(run?: Run | null) {
  if (!run?.attempts?.length) return "Not finished";
  const ms = run.attempts.reduce((total, attempt) => total + Number(attempt.execution?.duration_ms || 0), 0);
  return ms ? `${(ms / 1000).toFixed(2)} s` : "Not recorded";
}

function statusLabel(status = "") {
  if (status === "passed") return "Passed";
  if (status === "failed") return "Failed";
  if (status === "running" || status === "queued") return "Running";
  return "Error";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "passed") return <CheckCircle2 size={20} aria-hidden="true" />;
  if (status === "failed") return <XCircle size={20} aria-hidden="true" />;
  if (status === "running" || status === "queued") return <LoaderCircle size={20} className="spin" aria-hidden="true" />;
  return <AlertCircle size={20} aria-hidden="true" />;
}

function RunStatusToast({ run, onSelect, onDismiss }: { run?: Run; onSelect: (run: Run) => void; onDismiss: () => void }) {
  if (!run) return null;
  const active = run.status === "queued" || run.status === "running";
  const label = statusLabel(run.status);
  return <div className={`run-toast toast-${run.status}`} role="status" aria-live="polite">
    <div className="toast-icon"><StatusIcon status={run.status} /></div>
    <div className="toast-copy">
      <strong>{active ? "Run in progress" : `Run ${label.toLowerCase()}`}</strong>
      <span>{run.task_id || "Unnamed task"}{active ? " · verification running" : " · view result details"}</span>
    </div>
    <button className="toast-action" disabled={active} onClick={() => onSelect(run)}>{active ? "Working..." : "Inspect"}</button>
    {!active && <button className="toast-close" aria-label="Dismiss run status" onClick={onDismiss}><X size={15} /></button>}
  </div>;
}

function LoadingScreen({ error, onRetry }: { error?: string; onRetry?: () => void }) {
  return <main className="loading-screen" aria-live="polite">
    <div className="loading-card">
      <div className="loading-logo"><Activity size={25} /></div>
      <div className="loading-orbit"><span /><span /><span /></div>
      <div className="eyebrow">{error ? "CONNECTION INTERRUPTED" : "SECURE WORKSPACE"}</div>
      <h1>{error ? "Unable to connect" : "Connecting your workspace"}</h1>
      <p>{error || "Checking the API, database, benchmarks, and agent services before opening the dashboard."}</p>
      {!error && <div className="loading-steps"><span className="complete"><CheckCircle2 size={14} /> API</span><span><LoaderCircle size={14} className="spin" /> Database</span><span><LoaderCircle size={14} className="spin" /> Agent</span></div>}
      {error && onRetry && <button className="primary" onClick={onRetry}><RefreshCw size={15} /> Try again</button>}
    </div>
  </main>;
}

function downloadFile(filename: string, content: string, type = "application/json") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportRuns(runs: Run[]) {
  downloadFile(`verified-agent-runs-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(runs, null, 2));
}

function LatestResult({ run, onSelect }: { run?: Run; onSelect: (run: Run) => void }) {
  if (!run) return <section className="result-card result-empty"><div className="result-icon neutral"><Timer size={20} /></div><div><span className="result-kicker">LATEST TASK RESULT</span><h3>No runs yet</h3><p>Create a run to see a clear, plain-language outcome here.</p></div></section>;
  const label = statusLabel(run.status);
  return <section className={`result-card result-${run.status}`} aria-label={`Latest task result: ${label}`}>
    <div className="result-icon"><StatusIcon status={run.status} /></div>
    <div className="result-main"><span className="result-kicker">LATEST TASK RESULT</span><div className="result-heading"><h3>{run.task_id || "Unnamed task"}</h3><span className="status-badge">{label}</span></div><p>{run.error || (label === "Passed" ? "The task completed successfully." : label === "Running" ? "The agent is working through this task." : "Review the attempts and feedback for next steps.")}</p></div>
    <div className="result-meta"><span><b>{run.attempts?.length || 0}</b> attempts</span><span><b>{durationFor(run)}</b> execution time</span></div>
    <button className="outline-button" onClick={() => onSelect(run)}><Eye size={16} /> Inspect details</button>
  </section>;
}

function App() {
  const [view, setView] = useState("overview");
  const [summary, setSummary] = useState<any>({});
  const [runs, setRuns] = useState<Run[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [experiments, setExperiments] = useState<any[]>([]);
  const [memory, setMemory] = useState<any[]>([]);
  const [selected, setSelected] = useState<Run | null>(null);
  const [open, setOpen] = useState(true);
  const [modal, setModal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [initializing, setInitializing] = useState(true);
  const [dismissedToast, setDismissedToast] = useState<string | null>(null);

  const load = async () => {
    setBusy(true); setError("");
    try {
      const [s, r, _runtime, t, e, m] = await Promise.all([
        api<any>("/dashboard/summary"), api<any>("/runs?limit=50"),
        api<any>("/settings"),
        api<Task[]>("/benchmarks/tasks"), api<any>("/experiments/ablations"), api<any>("/memory"),
      ]);
      setSummary(s); setRuns(r.runs || []); setTasks(t || []);
      setExperiments(Array.isArray(e) ? e : Object.entries(e || {}).map(([name, result]) => ({ name, result })));
      setMemory(m || []);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load dashboard data."); }
    finally { setBusy(false); setInitializing(false); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!runs.some(r => r.status === "queued" || r.status === "running")) return;
    const timer = window.setInterval(async () => {
      try { const result = await api<any>("/runs?limit=50"); setRuns(result.runs || []); }
      catch { /* the next normal refresh will surface connection errors */ }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [runs]);

  const title = nav.find(([id]) => id === view)?.[1] || "Overview";
  const latestRun = runs[0];
  const inspectRun = (run: Run) => {
    setSelected(run);
    window.setTimeout(() => document.getElementById("run-detail")?.scrollIntoView({ behavior: "smooth", block: "center" }), 0);
  };
  if (initializing) return <LoadingScreen error={error || undefined} onRetry={error ? () => { setInitializing(true); load(); } : undefined} />;
  return <><RunStatusToast run={latestRun?.run_id === dismissedToast ? undefined : latestRun} onSelect={inspectRun} onDismiss={() => latestRun && setDismissedToast(latestRun.run_id)} /><div className="app">
    <aside className={open ? "sidebar" : "sidebar closed"}>
      <div className="brand"><div className="logo"><Activity size={17} /></div><div><b>VERIFIED</b><small>EXECUTION AGENT</small></div></div>
      <nav>{nav.map(([id, label, Icon]) => <button key={id} className={view === id ? "active" : ""} onClick={() => { setView(id); setSelected(null); }}><Icon size={17} />{label}</button>)}</nav>
      <div className="side-bottom"><span className="online"><i /> API connected</span></div>
    </aside>
    <main><header><button className="menu" aria-label="Toggle navigation" onClick={() => setOpen(!open)}><Menu /></button><div><div className="eyebrow">WORKSPACE / {title.toUpperCase()}</div><h1>Execution Dashboard</h1></div><div className="header-actions"><button className="icon-button" title="Export all run history" onClick={() => exportRuns(runs)} disabled={!runs.length}><Download size={15} /></button><button className="icon-button" title="Refresh dashboard" onClick={load} disabled={busy}><RefreshCw size={16} className={busy ? "spin" : ""} /></button><span className="live"><i /> LIVE</span></div></header>
      <section className="content">{error && <div className="alert"><strong>Could not load this view.</strong> {error}<button onClick={load}>Try again</button></div>}
        {view === "overview" && <Overview summary={summary} runs={runs} experiments={experiments} onRun={() => setModal(true)} onSelect={inspectRun} onRuns={() => setView("runs")} />}
        {view === "runs" && <Runs runs={runs} tasks={tasks} onSelect={inspectRun} onCreate={() => setModal(true)} />}
        {view === "experiments" && <Experiments items={experiments} />}
        {view === "memory" && <Memory items={memory} />}
        {view === "benchmarks" && <Benchmarks tasks={tasks} />}
        {view === "guide" && <Guide />}
        {view === "settings" && <SettingsView />}
        {selected && <RunDetail run={selected} onClose={() => setSelected(null)} />}
      </section>
    </main>
    {modal && createPortal(<RunModal tasks={tasks} onClose={() => setModal(false)} onCreated={async (id) => { setModal(false); const started = await api<Run>(`/runs/${id}`); setSelected(started); await load(); }} />, document.body)}
  </div></>;
}

function Cards({ summary }: { summary: any }) {
  const cards: [string, string, any, string][] = [
    ["PASS RATE", `${((summary.pass_rate || 0) * 100).toFixed(1)}%`, CheckCircle2, "green"],
    ["COMPLETED RUNS", `${summary.runs || 0}`, Activity, "purple"],
    ["TOKENS / COST", `${(summary.total_tokens || 0).toLocaleString()} / $${(summary.cost_usd || 0).toFixed(2)}`, CircleDollarSign, "amber"],
    ["AVERAGE LATENCY", `${Math.round(summary.avg_latency_ms || 0)} ms`, Clock3, "blue"],
  ];
  return <div className="cards">{cards.map(([label, value, Icon, color]) => <div className="card" key={label}><div className={`icon ${color}`}><Icon size={19} /></div><div><small>{label}</small><strong>{value}</strong><span className="muted">Persisted in SQLite</span></div></div>)}</div>;
}
function Overview({ summary, runs, experiments, onRun, onSelect, onRuns }: any) {
  const series = summary.pass_rate_series || [];
  const completed = summary.runs || runs.filter((run: Run) => run.status === "passed" || run.status === "failed").length;
  const active = runs.filter((run: Run) => run.status === "queued" || run.status === "running").length;
  const passRate = Math.round((summary.pass_rate || 0) * 100);
  const totalTokens = Number(summary.total_tokens || 0);
  return <><div className="welcome"><div><div className="eyebrow">VERIFIED WORKSPACE</div><h2>Welcome back, <span>operator</span></h2><p>Monitor generated code, verified execution, and learning signals.</p></div><button className="primary" onClick={onRun}><Plus size={16} /> New run</button></div>
    <div className="ticker-grid">
      <section className="ticker-card"><div className="ticker-icon cyan"><Activity size={15} /></div><div><span>EXECUTION HEALTH</span><strong>{passRate}%</strong><small>verified pass rate</small></div><b className="ticker-change">{passRate >= 70 ? "GOOD" : "BUILDING"}</b></section>
      <section className="ticker-card"><div className="ticker-icon blue"><CheckCircle2 size={15} /></div><div><span>COMPLETED RUNS</span><strong>{completed}</strong><small>persisted benchmark runs</small></div><b className="ticker-change">{active} ACTIVE</b></section>
      <section className="ticker-card"><div className="ticker-icon teal"><CircleDollarSign size={15} /></div><div><span>TOKEN USAGE</span><strong>{totalTokens.toLocaleString()}</strong><small>provider tokens recorded</small></div><b className="ticker-change">LIVE</b></section>
    </div>
    <div className="dashboard-grid"><section className="panel chart dashboard-chart"><div className="panel-title"><div><h3>Verification trend</h3><p>Pass rate across recorded completed runs</p></div><button className="more" onClick={() => window.alert("The chart uses every completed run saved in the database.")}>This week</button></div><div className="chart-area"><div className="ylabels"><span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0%</span></div><div className="graph"><div className="gridlines">{[1, 2, 3, 4].map(x => <i key={x} />)}</div>{series.length > 1 ? <svg viewBox="0 0 600 180" preserveAspectRatio="none"><polyline fill="none" stroke="#19c9e9" strokeWidth="3" points={series.map((p: any, i: number) => `${i * (600 / Math.max(series.length - 1, 1))},${170 - Number(p.value) * 140}`).join(" ")} /></svg> : <div className="chart-empty">Complete more runs to see the trend.</div>}<div className="xlabels"><span>Mon</span><span>Wed</span><span>Fri</span><span>Sun</span></div></div></div></section><div className="side-stack"><section className="panel balance-card"><div className="panel-title"><div><span className="card-kicker">WORKSPACE SUMMARY</span><h3>Current balance</h3></div><CalendarDays size={15} /></div><strong className="balance-value">{completed}</strong><span className="balance-label">verified runs</span><div className="balance-row"><span>Pass rate</span><b>{passRate}%</b></div><div className="balance-row"><span>Active now</span><b>{active}</b></div></section><section className="panel action-card"><div className="panel-title"><div><span className="card-kicker">LEARNING MEMORY</span><h3>Improve the agent</h3></div><Brain size={15} /></div><p>{experiments.length ? `${experiments.length} saved comparisons available.` : "Successful fixes are retained for future retrieval."}</p><button className="primary" onClick={onRuns}>Inspect runs <ArrowUpRight size={13} /></button></section></div></div>
    <div className="section-heading"><div><h3>Recent verified activity</h3><p>Latest generated solutions and execution outcomes.</p></div><button className="link" onClick={onRuns}>View all <ArrowUpRight size={13} /></button></div>
    <LatestResult run={runs[0]} onSelect={onSelect} /><RunTable runs={runs.slice(0, 6)} onSelect={onSelect} onRuns={onRuns} /></>;
}
function MetricBar({ item }: any) { const metrics = item.metrics || item.result?.metrics || {}; const value = Number(metrics["pass@k"] ?? metrics["pass@1"] ?? 0) * 100; return <div className="barrow"><span>{item.name || "Configuration"}</span><div><i style={{ width: `${Math.min(100, value)}%` }} /></div><b>{value.toFixed(0)}%</b></div>; }
function RunTable({ runs, onSelect, onRuns }: any) { return <section className="panel runs"><div className="panel-title"><div><h3>Recent verified activity</h3><p>Past executions, outcomes, and feedback are persisted here.</p></div><div className="panel-actions"><button className="icon-button" title="Download run history" onClick={() => exportRuns(runs)} disabled={!runs.length}><Download size={14} /></button><button className="link" onClick={onRuns}>View all</button></div></div><table><thead><tr><th>RUN</th><th>TASK</th><th>STATUS</th><th>ATTEMPTS</th><th>TIME</th></tr></thead><tbody>{runs.length ? runs.map((r: Run) => <tr onClick={() => onSelect(r)} key={r.run_id}><td className="mono">#{r.run_id.slice(0, 8)}</td><td>{r.task_id || "Unknown task"}</td><td><span className={`status ${r.status}`}><i />{r.status}</span></td><td>{r.attempts?.length || "—"}</td><td>{r.created_at ? new Date(r.created_at).toLocaleString() : "Queued"}</td></tr>) : <tr><td colSpan={5} className="empty">No runs yet. Create one to start the verification loop.</td></tr>}</tbody></table></section>; }
function Runs({ runs, tasks, onSelect, onCreate }: any) { return <><div className="welcome"><div><h2>Runs</h2><p>Start and inspect benchmark tasks. Running jobs update automatically.</p></div><div className="welcome-actions"><button className="outline-button" onClick={() => exportRuns(runs)} disabled={!runs.length}><Download size={14} /> Export history</button><button className="primary" onClick={onCreate}><Plus size={16} /> New run</button></div></div><LatestResult run={runs[0]} onSelect={onSelect} /><RunTable runs={runs} onSelect={onSelect} onRuns={() => {}} /><p className="help"><Play size={14} /> Available tasks: {tasks.length}. A run may take a minute when an LLM provider is configured.</p></>; }
function Experiments({ items }: any) { return <><div className="welcome"><div><h2>Experiments</h2><p>Persisted ablation results let you compare configurations without rerunning them.</p></div></div><section className="panel">{items.length ? <table><thead><tr><th>NAME</th><th>CONFIGURATION</th><th>RESULT</th><th>SAVED</th></tr></thead><tbody>{items.map((x: any, i: number) => <tr key={i}><td>{x.name || "Experiment"}</td><td className="mono">{JSON.stringify(x.config || {})}</td><td>{JSON.stringify(x.result || x.metrics || {})}</td><td>{x.created_at ? new Date(x.created_at).toLocaleString() : "Persisted file"}</td></tr>)}</tbody></table> : <Empty text="No saved ablation results. Run the offline evaluation command described in README, then refresh." />}</section></>; }
function Memory({ items }: any) { return <><div className="welcome"><div><h2>Memory</h2><p>Successful solutions are retained to help later runs learn from previous work.</p></div></div><section className="panel">{items.length ? <table><thead><tr><th>KEY</th><th>TASK</th><th>OUTCOME</th><th>SAVED</th></tr></thead><tbody>{items.map((x: any) => <tr key={x.key}><td className="mono">{x.key}</td><td>{x.task_id || "General"}</td><td><span className="status passed"><i />{x.successful ? "Successful" : "Unsuccessful"}</span></td><td>{new Date(x.created_at).toLocaleString()}</td></tr>)}</tbody></table> : <Empty text="Memory is empty. Passed runs will add useful solutions here." />}</section></>; }
function Benchmarks({ tasks }: any) { return <><div className="welcome"><div><h2>Benchmarks</h2><p>Tasks are small programming problems used to verify generated code.</p></div></div><section className="panel"><table><thead><tr><th>TASK</th><th>DESCRIPTION</th><th>SPLIT</th><th>CATEGORY</th></tr></thead><tbody>{tasks.length ? tasks.map((t: Task) => <tr key={t.id}><td className="mono">{t.id}</td><td>{t.prompt}</td><td>{t.split || "train"}</td><td>{t.category || "general"}</td></tr>) : <tr><td colSpan={4} className="empty">No benchmark tasks were found.</td></tr>}</tbody></table></section></>; }
function SettingsView() {
  const apiUrl = API_BASE || "same origin (FastAPI serves the dashboard)";
  const [runtime, setRuntime] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<any>("/settings").then(setRuntime).catch(err => setError(err instanceof Error ? err.message : "Unable to read runtime settings.")); }, []);
  return <><div className="welcome"><div><div className="eyebrow">RUNTIME STATUS</div><h2>Settings</h2><p>Live connection and deployment information. Secrets are never displayed here.</p></div></div>
    <div className="settings-grid">
      <section className="panel settings-card"><Server size={20} /><span>API status</span><strong>{runtime ? "Connected" : error ? "Unavailable" : "Checking..."}</strong><small>{apiUrl}</small></section>
      <section className="panel settings-card"><Database size={20} /><span>Database</span><strong>{runtime?.database || "Checking..."}</strong><small>{runtime?.database_path || "Managed production storage"}</small></section>
      <section className="panel settings-card"><ShieldCheck size={20} /><span>Provider</span><strong>{runtime?.llm_provider || "Checking..."}</strong><small>Secrets remain on the backend</small></section>
      <section className="panel settings-card"><Workflow size={20} /><span>Executor</span><strong>{runtime?.docker_enabled ? "Docker enabled" : "Local subprocess"}</strong><small>Verified Python test execution</small></section>
    </div>
    <section className="panel settings"><label>API address <input readOnly value={apiUrl} /></label><label>Database mode <input readOnly value={runtime?.database || "SQLite locally · PostgreSQL in production"} /></label><label>Dashboard mode <input readOnly value="React + Vite frontend · FastAPI backend" /></label>{error && <p className="help">{error}</p>}<p className="help"><Server size={14} /> Configure provider keys and database paths on the backend environment, not in the browser.</p></section></>;
}
function Guide() { return <><div className="welcome"><div><div className="eyebrow">START HERE</div><h2>How the agent works</h2><p>A plain-language guide to every dashboard area and the verified execution loop.</p></div></div><div className="guide-grid"><section className="panel guide-card"><Workflow size={22} /><h3>What this project is</h3><p>This is an AI coding agent that generates Python, executes it against real tests, reads the actual test output, and retries when verification fails. The test runner—not the language model—decides whether a solution passes.</p></section><section className="panel guide-card"><ShieldCheck size={22} /><h3>The execution loop</h3><ol><li>Planner turns the task into an implementation plan.</li><li>Coder generates runnable Python.</li><li>Executor runs it in an isolated temporary workspace with pytest.</li><li>Critic converts failures into structured feedback.</li><li>Memory stores successful solutions for later retrieval.</li></ol></section><section className="panel guide-card"><LayoutDashboard size={22} /><h3>Dashboard areas</h3><p><b>Overview</b> shows health, pass rate, token usage, trend, and the latest result. <b>Runs</b> lists every execution and lets you inspect generated code, stdout, stderr, and attempts.</p><p><b>Experiments</b> shows ablation results. <b>Memory</b> shows successful stored solutions. <b>Benchmarks</b> lists verified tasks. <b>Settings</b> shows safe connection information.</p></section><section className="panel guide-card"><Database size={22} /><h3>What the numbers mean</h3><p><b>Execution health</b> is the percentage of completed runs that passed. <b>Completed runs</b> counts persisted passed and failed runs. <b>Token usage</b> comes from the configured LLM provider. <b>Verification trend</b> plots recorded pass outcomes over time.</p></section><section className="panel guide-card"><BookOpen size={22} /><h3>How to run a task</h3><ol><li>Click <b>New run</b>.</li><li>Choose a benchmark task such as <code>add</code> or <code>reverse</code>.</li><li>Choose <b>Baseline</b> for a cheap provider smoke test, or <b>Full system</b> to use structured feedback and memory.</li><li>Start with one attempt. Increase attempts only when you want retry behavior.</li><li>Read the latest result and open <b>Inspect details</b> for the evidence.</li></ol></section><section className="panel guide-card"><Server size={22} /><h3>Deployment model</h3><p>Vercel hosts the React interface, Render hosts FastAPI, Neon PostgreSQL stores production runs and metrics, and Gemini generates plans and code. Provider keys and database credentials stay on Render and are never sent to the browser.</p></section></div></>; }
function Empty({ text }: { text: string }) { return <div className="empty-block"><Brain size={22} /><p>{text}</p></div>; }
function RunDetail({ run, onClose }: { run: Run; onClose: () => void }) { return <section id="run-detail" className="detail"><button className="close" title="Close details" onClick={onClose}><X size={17} /></button><div className="detail-heading"><div><span className="card-kicker">EXECUTION LOG</span><h3>Run #{run.run_id.slice(0, 8)}</h3></div><button className="icon-button" title="Download this run" onClick={() => downloadFile(`run-${run.run_id}.json`, JSON.stringify(run, null, 2))}><Download size={14} /></button></div><p>{run.task_id} · <span className={`status ${run.status}`}><i />{run.status}</span></p>{run.error && <div className="alert">{run.error}</div>}{run.attempts?.map((a: any) => <div className="attempt" key={a.number}><b>Attempt {a.number}</b><span className={`status ${a.critique?.passed ? "passed" : "failed"}`}><i />{a.critique?.passed ? "Passed" : "Failed"}</span><pre>{a.critique?.summary || "No feedback available."}</pre>{a.execution?.stdout && <details><summary>stdout</summary><pre>{a.execution.stdout}</pre></details>}{a.execution?.stderr && <details><summary>stderr</summary><pre>{a.execution.stderr}</pre></details>}{a.code && <details><summary>generated code</summary><pre>{a.code}</pre></details>}</div>)}</section>; }
function RunModal({ tasks, onClose, onCreated }: { tasks: Task[]; onClose: () => void; onCreated: (id: string) => void }) { const [task, setTask] = useState(tasks[0]?.id || ""); const [config, setConfig] = useState("full_system"); const [attempts, setAttempts] = useState(3); const [saving, setSaving] = useState(false); const [error, setError] = useState(""); const submit = async (e: FormEvent) => { e.preventDefault(); if (!task) { setError("No benchmark tasks are available. Refresh the dashboard and try again."); return; } setSaving(true); setError(""); try { const result = await api<Run>("/runs", { method: "POST", body: JSON.stringify({ task_id: task, config, max_attempts: attempts }) }); onCreated(result.run_id); } catch (err) { setError(err instanceof Error ? err.message : "Could not create run."); } finally { setSaving(false); } }; return <div className="modal-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><form className="modal" onSubmit={submit}><button type="button" className="close" title="Close" onClick={onClose}><X size={17} /></button><span className="card-kicker">VERIFIED EXECUTION</span><h2>Start a new run</h2><p>The agent writes a solution, runs its tests, and retries with structured feedback.</p><label>Benchmark task<select value={task} onChange={e => setTask(e.target.value)} required disabled={!tasks.length}><option value="">{tasks.length ? "Select a benchmark task" : "No tasks available"}</option>{tasks.map(t => <option key={t.id} value={t.id}>{t.id} — {t.prompt.slice(0, 70)}</option>)}</select></label><label>Configuration<select value={config} onChange={e => setConfig(e.target.value)}><option value="full_system">Full system — feedback + memory</option><option value="memory">With memory</option><option value="baseline">Baseline — one generation</option></select></label><label>Maximum attempts<input type="number" min="1" max="10" value={attempts} onChange={e => setAttempts(Number(e.target.value))} /></label>{error && <div className="alert">{error}</div>}<button className="primary" disabled={saving || !task}>{saving ? "Starting..." : "Start run"}</button></form></div>; }
createRoot(document.getElementById("root")!).render(<App />);

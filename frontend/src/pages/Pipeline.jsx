import { useState, useEffect, useRef, useCallback } from "react";
import {
  startPipeline, getPipelineProgress, expandQuery, getActivePipelines,
} from "../api/client";

const STAGE_ICONS = {
  starting: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  searching: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z",
  crawling: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
  saving: "M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4",
  enriching: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  scoring: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  completed: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  failed: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z",
};

const STAGE_COLORS = {
  starting: "text-gray-400",
  searching: "text-blue-500",
  crawling: "text-indigo-500",
  saving: "text-green-500",
  enriching: "text-yellow-500",
  scoring: "text-purple-500",
  completed: "text-green-500",
  failed: "text-red-500",
};

const PRESET_QUERIES = [
  "Palm Oil Buyers India",
  "Sunflower Oil Distributors Maharashtra",
  "Refined Oil Manufacturers Gujarat",
  "CP10 Buyers India",
  "Bakery Manufacturers Karnataka",
  "Soap Manufacturers Tamil Nadu",
  "Food Manufacturers Delhi",
  "Vanaspati Manufacturers India",
  "Snack Manufacturers India",
  "Edible Oil Importers India",
];

function ProgressBar({ progress }) {
  if (!progress) return null;
  const pct = progress.total_queries > 0
    ? Math.round((progress.completed_queries / progress.total_queries) * 100)
    : 0;

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {progress.status === "completed" ? "Complete" :
           progress.status === "failed" ? "Failed" :
           `${progress.completed_queries}/${progress.total_queries} queries`}
        </span>
        <span className="text-sm text-gray-500">{pct}%</span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-dark-700 rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full transition-all duration-500 ${
            progress.status === "completed" ? "bg-green-500" :
            progress.status === "failed" ? "bg-red-500" :
            "bg-indigo-500 animate-pulse"
          }`}
          style={{ width: `${pct}%` }}
        ></div>
      </div>
    </div>
  );
}

function LiveStats({ progress }) {
  if (!progress) return null;
  const stats = [
    { label: "Companies Found", value: progress.companies_found, color: "text-indigo-600" },
    { label: "New", value: progress.companies_new, color: "text-green-600" },
    { label: "Duplicates", value: progress.companies_duplicate, color: "text-yellow-600" },
    { label: "Emails", value: progress.emails_found, color: "text-blue-600" },
    { label: "Phones", value: progress.phones_found, color: "text-purple-600" },
    { label: "Websites", value: progress.websites_found, color: "text-teal-600" },
    { label: "Enriched", value: progress.enriched, color: "text-orange-600" },
    { label: "Errors", value: progress.errors, color: "text-red-600" },
  ];

  return (
    <div className="grid grid-cols-4 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="text-center p-2 rounded-lg bg-gray-50 dark:bg-dark-700">
          <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
          <p className="text-xs text-gray-500">{s.label}</p>
        </div>
      ))}
    </div>
  );
}

function LogFeed({ messages }) {
  const feedRef = useRef(null);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  if (!messages || messages.length === 0) {
    return (
      <p className="text-center text-gray-400 text-sm py-8">
        Search results will appear here...
      </p>
    );
  }

  return (
    <div ref={feedRef} className="space-y-1.5 max-h-[400px] overflow-y-auto p-3 bg-gray-50 dark:bg-dark-800 rounded-lg">
      {messages.map((msg, i) => (
        <div key={i} className="flex items-start gap-2 text-sm">
          <span className="text-gray-400 text-xs shrink-0 mt-0.5">
            {new Date(msg.time).toLocaleTimeString()}
          </span>
          <span className="text-gray-700 dark:text-gray-300">{msg.message}</span>
        </div>
      ))}
    </div>
  );
}

export default function Pipeline() {
  const [query, setQuery] = useState("");
  const [maxQueries, setMaxQueries] = useState(50);
  const [maxPages, setMaxPages] = useState(3);
  const [selectedSources, setSelectedSources] = useState([]);
  const [skipEnrich, setSkipEnrich] = useState(false);
  const [skipScore, setSkipScore] = useState(false);

  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(null);
  const [preview, setPreview] = useState(null);
  const [showPreview, setShowPreview] = useState(false);

  const eventSourceRef = useRef(null);
  const progressIntervalRef = useRef(null);

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  const handleSearch = async () => {
    if (!query.trim()) return;

    cleanup();
    setRunning(true);
    setProgress(null);

    try {
      const res = await startPipeline({
        query: query.trim(),
        max_queries: maxQueries,
        max_pages_per_spider: maxPages,
        sources: selectedSources.length > 0 ? selectedSources : null,
        skip_enrich: skipEnrich,
        skip_score: skipScore,
      });

      const runId = res.data.run_id;

      // Connect SSE for live updates
      const es = new EventSource(`/api/pipeline/${runId}/stream`);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setProgress(data);
          if (data.status === "completed" || data.status === "failed") {
            es.close();
            setRunning(false);
          }
        } catch (e) {
          console.error("SSE error:", e);
        }
      };

      es.onerror = () => {
        // Fallback to polling
        es.close();
        progressIntervalRef.current = setInterval(async () => {
          try {
            const res = await getPipelineProgress(runId);
            setProgress(res.data);
            if (res.data.status === "completed" || res.data.status === "failed") {
              clearInterval(progressIntervalRef.current);
              setRunning(false);
            }
          } catch (e) {
            clearInterval(progressIntervalRef.current);
            setRunning(false);
          }
        }, 2000);
      };

    } catch (err) {
      console.error("Pipeline start error:", err);
      setRunning(false);
    }
  };

  const handlePreview = async () => {
    if (!query.trim()) return;
    try {
      const res = await expandQuery(query.trim());
      setPreview(res.data);
      setShowPreview(true);
    } catch (err) {
      console.error("Preview error:", err);
    }
  };

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Lead Discovery Pipeline
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          Search for buyers, discover companies, enrich data, score leads — all in one pipeline.
        </p>
      </div>

      {/* Search Form */}
      <div className="glass-card p-6 mb-6">
        <div className="flex gap-3 mb-4">
          <div className="flex-1 relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !running && handleSearch()}
              placeholder='e.g. "Palm Oil Buyers India" or "Food Manufacturers Karnataka"'
              className="w-full px-4 py-3 pl-10 rounded-xl border border-gray-200 dark:border-dark-600 bg-white dark:bg-dark-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              disabled={running}
            />
            <svg className="w-5 h-5 text-gray-400 absolute left-3 top-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <button
            onClick={handleSearch}
            disabled={running || !query.trim()}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running ? (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Running...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Discover Leads
              </span>
            )}
          </button>
          <button
            onClick={handlePreview}
            disabled={!query.trim()}
            className="btn-secondary disabled:opacity-50"
          >
            Preview Queries
          </button>
        </div>

        {/* Quick presets */}
        <div className="flex flex-wrap gap-2 mb-4">
          {PRESET_QUERIES.map((preset) => (
            <button
              key={preset}
              onClick={() => setQuery(preset)}
              className="text-xs px-3 py-1.5 rounded-full bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-400 hover:bg-brand-100 dark:hover:bg-brand-900/30 hover:text-brand-600 transition-colors"
            >
              {preset}
            </button>
          ))}
        </div>

        {/* Settings row */}
        <div className="flex flex-wrap items-center gap-4 pt-3 border-t border-gray-100 dark:border-dark-600">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-500">Max Queries:</label>
            <select
              value={maxQueries}
              onChange={(e) => setMaxQueries(Number(e.target.value))}
              className="text-sm border rounded-lg px-2 py-1 bg-white dark:bg-dark-800 dark:border-dark-600"
              disabled={running}
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-500">Pages/Spider:</label>
            <select
              value={maxPages}
              onChange={(e) => setMaxPages(Number(e.target.value))}
              className="text-sm border rounded-lg px-2 py-1 bg-white dark:bg-dark-800 dark:border-dark-600"
              disabled={running}
            >
              <option value={1}>1</option>
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
            </select>
          </div>
          <label className="flex items-center gap-1.5 text-sm text-gray-500 cursor-pointer">
            <input type="checkbox" checked={skipEnrich} onChange={(e) => setSkipEnrich(e.target.checked)} disabled={running} className="rounded" />
            Skip Enrich
          </label>
          <label className="flex items-center gap-1.5 text-sm text-gray-500 cursor-pointer">
            <input type="checkbox" checked={skipScore} onChange={(e) => setSkipScore(e.target.checked)} disabled={running} className="rounded" />
            Skip Score
          </label>
        </div>
      </div>

      {/* Preview Panel */}
      {showPreview && preview && (
        <div className="glass-card p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900 dark:text-white">
              Search Variations ({preview.total_variations} total)
            </h3>
            <button onClick={() => setShowPreview(false)} className="text-gray-400 hover:text-gray-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-[300px] overflow-y-auto">
            {preview.variations.map((v, i) => (
              <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 dark:bg-dark-700 text-sm">
                <span className="w-5 h-5 rounded-full bg-brand-100 dark:bg-brand-900/30 text-brand-600 text-xs flex items-center justify-center shrink-0">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-gray-700 dark:text-gray-300 truncate">{v.query}</p>
                  <p className="text-xs text-gray-400">{v.source} &middot; {v.intent}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Live Progress */}
      {progress && (
        <div className="glass-card p-5 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className={`p-2 rounded-lg ${
              progress.status === "completed" ? "bg-green-100 dark:bg-green-900/30" :
              progress.status === "failed" ? "bg-red-100 dark:bg-red-900/30" :
              "bg-indigo-100 dark:bg-indigo-900/30"
            }`}>
              <svg className={`w-5 h-5 ${STAGE_COLORS[progress.status] || "text-gray-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={STAGE_ICONS[progress.status] || STAGE_ICONS.starting} />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-gray-900 dark:text-white capitalize">
                {progress.status === "completed" ? "Pipeline Complete" :
                 progress.status === "failed" ? "Pipeline Failed" :
                 `Stage: ${progress.status}`}
              </h3>
              <p className="text-sm text-gray-500">
                {progress.current_query && `Current: "${progress.current_query}"`}
                {progress.current_source && ` on ${progress.current_source}`}
              </p>
            </div>
            <div className="text-right text-sm text-gray-500">
              <p>{Math.round(progress.elapsed)}s elapsed</p>
              {progress.status === "completed" || progress.status === "failed" ? null : (
                <p className="text-xs text-gray-400">Query {progress.completed_queries}/{progress.total_queries}</p>
              )}
            </div>
          </div>

          <ProgressBar progress={progress} />
          <div className="mt-4">
            <LiveStats progress={progress} />
          </div>
        </div>
      )}

      {/* Live Log Feed */}
      {progress && progress.messages && (
        <div className="glass-card p-5">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-3">Live Log</h3>
          <LogFeed messages={progress.messages} />
        </div>
      )}
    </div>
  );
}

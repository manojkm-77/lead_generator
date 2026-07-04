import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { getBuyerIntelligence, getIntelligenceStats, analyzeAll } from "../api/intelligence";

function StatCard({ label, value, subtitle, color = "primary" }) {
  const colors = {
    primary: "from-brand-500 to-brand-700",
    green: "from-green-500 to-emerald-600",
    yellow: "from-yellow-500 to-orange-500",
    red: "from-red-500 to-pink-600",
    blue: "from-blue-500 to-indigo-600",
    purple: "from-purple-500 to-pink-600",
  };
  return (
    <div className="glass-card p-4 group hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{label}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
        </div>
        <div className={`w-2 h-8 rounded-full bg-gradient-to-b ${colors[color]} group-hover:scale-y-110 transition-transform`}></div>
      </div>
    </div>
  );
}

function ScoreBar({ score }) {
  const color = score >= 70 ? "bg-green-500" : score >= 50 ? "bg-yellow-500" : score >= 30 ? "bg-orange-500" : "bg-gray-400";
  return (
    <div className="w-full bg-gray-200 dark:bg-dark-700 rounded-full h-2">
      <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${score}%` }}></div>
    </div>
  );
}

function PriorityBadge({ priority }) {
  const colors = {
    A: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    B: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    C: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    D: "bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-gray-400",
  };
  return <span className={`px-2 py-0.5 rounded text-xs font-bold ${colors[priority] || colors.D}`}>{priority}</span>;
}

function TempBadge({ temp }) {
  const colors = {
    "Hot": "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    "Very Hot": "bg-red-200 text-red-800 dark:bg-red-900/50 dark:text-red-300",
    "Warm": "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    "Cold": "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  };
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[temp] || colors.Cold}`}>{temp}</span>;
}

function ScoreGauge({ score, size = 60 }) {
  const r = size / 2 - 4;
  const s = 4;
  const nr = r - s;
  const c = nr * 2 * Math.PI;
  const offset = c - (score / 100) * c;
  const color = score >= 70 ? "#22c55e" : score >= 50 ? "#f59e0b" : score >= 30 ? "#f97316" : "#6b7280";
  return (
    <div className="relative inline-flex items-center justify-center">
      <svg height={size} width={size}>
        <circle stroke="#e5e7eb" fill="transparent" strokeWidth={s} r={nr} cx={size / 2} cy={size / 2} className="dark:stroke-dark-700" />
        <circle stroke={color} fill="transparent" strokeWidth={s} strokeLinecap="round"
          strokeDasharray={c + " " + c} style={{ strokeDashoffset: offset, transition: "stroke-dashoffset 0.5s ease" }}
          r={nr} cx={size / 2} cy={size / 2} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div className="absolute text-center">
        <p className="text-lg font-bold text-gray-900 dark:text-white">{score}</p>
      </div>
    </div>
  );
}

export default function BuyerIntelligence() {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [filter, setFilter] = useState({ priority: "", min_score: 0, industry: "" });
  const [showAnalyzeMsg, setShowAnalyzeMsg] = useState(false);

  const fetchData = useCallback(() => {
    setLoading(true);
    const params = { page, page_size: 20, ...filter };
    Object.keys(params).forEach((k) => {
      if (params[k] === "" || params[k] === null || params[k] === undefined || params[k] === 0) {
        if (k !== "min_score") delete params[k];
      }
    });
    Promise.all([
      getBuyerIntelligence(params).catch(() => ({ data: { items: [], total: 0 } })),
      getIntelligenceStats().catch(() => ({ data: null })),
    ])
      .then(([i, s]) => { setItems(i.data.items); setTotal(i.data.total); setStats(s.data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, filter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAnalyzeAll = async () => {
    setAnalyzing(true);
    setShowAnalyzeMsg(false);
    try {
      await analyzeAll({ limit: 50 });
      setShowAnalyzeMsg(true);
    } catch {}
    setTimeout(() => { setAnalyzing(false); }, 5000);
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Buyer Intelligence</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">AI-powered buyer scoring and recommendations</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleAnalyzeAll} disabled={analyzing}
            className="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-brand-500 to-brand-600 rounded-lg hover:from-brand-600 hover:to-brand-700 disabled:opacity-50 transition-all">
            {analyzing ? (
              <span className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                Analyzing...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                Analyze All
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Analyze Message */}
      {showAnalyzeMsg && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3 text-sm text-green-700 dark:text-green-400">
          Batch analysis queued. Results will appear shortly. Refresh in a few seconds.
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard label="Analyzed" value={stats.analyzed} subtitle={`of ${stats.total_companies}`} color="primary" />
          <StatCard label="Contacts Found" value={stats.contacts_found} color="green" />
          <StatCard label="Products Detected" value={stats.products_detected} color="yellow" />
          <StatCard label="Analysis Rate" value={`${stats.analysis_rate}%`} color="blue" />
          <StatCard label="Priority A" value={stats.priority_distribution?.A || 0} subtitle="Top buyers" color="green" />
          <StatCard label="Priority B" value={stats.priority_distribution?.B || 0} subtitle="Good potential" color="blue" />
        </div>
      )}

      {/* Filters */}
      <div className="glass-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Filters:</span>
          <select className="input text-sm py-1.5 w-32" value={filter.priority}
            onChange={(e) => { setFilter({ ...filter, priority: e.target.value }); setPage(1); }}>
            <option value="">All Priority</option>
            <option value="A">Priority A</option>
            <option value="B">Priority B</option>
            <option value="C">Priority C</option>
            <option value="D">Priority D</option>
          </select>
          <select className="input text-sm py-1.5 w-36" value={filter.industry}
            onChange={(e) => { setFilter({ ...filter, industry: e.target.value }); setPage(1); }}>
            <option value="">All Industries</option>
            <option value="Food Manufacturer">Food Manufacturer</option>
            <option value="Bakery">Bakery</option>
            <option value="Distributor">Distributor</option>
            <option value="Wholesaler">Wholesaler</option>
            <option value="Restaurant">Restaurant</option>
            <option value="Hotel">Hotel</option>
          </select>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Min Score:</span>
            <input type="number" className="input text-sm py-1.5 w-20" value={filter.min_score || ""}
              onChange={(e) => { setFilter({ ...filter, min_score: parseInt(e.target.value) || 0 }); setPage(1); }}
              placeholder="0" />
          </div>
          <span className="text-xs text-gray-400">{total} results</span>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="glass-card p-8">
          <div className="space-y-3">
            {Array(5).fill(0).map((_, i) => (
              <div key={i} className="animate-pulse flex items-center gap-4">
                <div className="w-10 h-10 bg-gray-200 dark:bg-dark-700 rounded-lg"></div>
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 dark:bg-dark-700 rounded w-1/4"></div>
                  <div className="h-3 bg-gray-200 dark:bg-dark-700 rounded w-1/6"></div>
                </div>
                <div className="h-6 w-12 bg-gray-200 dark:bg-dark-700 rounded"></div>
              </div>
            ))}
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <p className="text-gray-900 dark:text-white font-semibold">No intelligence data yet</p>
          <p className="text-sm text-gray-500 mt-1 mb-4">Click "Analyze All" to run AI scoring on your companies</p>
          <button onClick={handleAnalyzeAll} disabled={analyzing}
            className="px-6 py-2 text-sm font-medium text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50">
            {analyzing ? "Analyzing..." : "Start Analysis"}
          </button>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 dark:border-dark-700 bg-gray-50/50 dark:bg-dark-800/50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Company</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Score</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Priority</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Temperature</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Industry</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Consumption</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Size</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Maturity</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.company_id} className="table-row border-b border-gray-100 dark:border-dark-700/50">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <ScoreGauge score={item.buyer_score} size={40} />
                        <div>
                          <Link to={`/intelligence/${item.company_id}`} className="font-medium text-gray-900 dark:text-white hover:text-brand-600 dark:hover:text-brand-400 text-sm">
                            {item.company_name}
                          </Link>
                          <p className="text-xs text-gray-400">{item.city || "Unknown location"}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-gray-900 dark:text-white w-8">{item.buyer_score}</span>
                        <div className="w-20"><ScoreBar score={item.buyer_score} /></div>
                      </div>
                    </td>
                    <td className="px-5 py-3"><PriorityBadge priority={item.buyer_priority} /></td>
                    <td className="px-5 py-3"><TempBadge temp={item.lead_temperature} /></td>
                    <td className="px-5 py-3 text-sm text-gray-600 dark:text-gray-400">{item.industry || "-"}</td>
                    <td className="px-5 py-3 text-sm text-gray-600 dark:text-gray-400">{item.annual_consumption || "-"}</td>
                    <td className="px-5 py-3 text-sm text-gray-600 dark:text-gray-400">{item.company_size || "-"}</td>
                    <td className="px-5 py-3 text-sm text-gray-600 dark:text-gray-400">{item.procurement_maturity || "-"}</td>
                    <td className="px-5 py-3">
                      <Link to={`/intelligence/${item.company_id}`} className="text-xs text-brand-600 hover:text-brand-700 font-medium px-2 py-1 rounded hover:bg-brand-50 dark:hover:bg-brand-900/20">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-5 py-3 border-t border-gray-200 dark:border-dark-700">
              <p className="text-xs text-gray-500">Showing {((page - 1) * 20) + 1} to {Math.min(page * 20, total)} of {total}</p>
              <div className="flex items-center gap-1">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-2 py-1 text-xs border border-gray-200 dark:border-dark-700 rounded disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-dark-700">Prev</button>
                <span className="px-3 py-1 text-xs text-gray-500">{page} / {totalPages}</span>
                <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="px-2 py-1 text-xs border border-gray-200 dark:border-dark-700 rounded disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-dark-700">Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

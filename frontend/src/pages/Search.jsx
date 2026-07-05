import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { globalSearch, startPipeline, expandQuery } from "../api/client";

const SUGGESTIONS = [
  { text: "Palm Oil Buyers India", category: "Edible Oil" },
  { text: "Food Manufacturers Karnataka", category: "Food" },
  { text: "Edible Oil Distributors Mumbai", category: "Edible Oil" },
  { text: "Soap Manufacturers Gujarat", category: "Soap" },
  { text: "CP10 Importers India", category: "Edible Oil" },
  { text: "Bakery Manufacturers Delhi", category: "Food" },
  { text: "Restaurants Hyderabad", category: "Food Service" },
  { text: "Hotels Bangalore", category: "Hospitality" },
  { text: "Snack Manufacturers India", category: "Food" },
  { text: "Vegetable Oil Importers", category: "Edible Oil" },
];

export default function Search() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("pipeline");
  const [quickResults, setQuickResults] = useState(null);
  const [preview, setPreview] = useState(null);
  const [showPreview, setShowPreview] = useState(false);

  const handleFullDiscovery = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await startPipeline({
        query: query.trim(),
        max_queries: 500,
        max_pages_per_spider: 3,
      });
      navigate("/discovery", {
        state: {
          runId: res.data.run_id,
          query: query.trim(),
          autoStart: true,
        },
      });
    } catch (err) {
      console.error("Pipeline error:", err);
      setLoading(false);
    }
  }, [query, navigate]);

  const handlePreview = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await expandQuery(query.trim(), 100);
      setPreview(res.data);
      setShowPreview(true);
    } catch (err) {
      console.error("Preview error:", err);
    } finally {
      setLoading(false);
    }
  }, [query]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    if (mode === "pipeline") {
      handleFullDiscovery();
    } else {
      setLoading(true);
      globalSearch({ q: query.trim(), limit: 20 })
        .then((res) => setQuickResults(res.data))
        .catch((err) => console.error("Search error:", err))
        .finally(() => setLoading(false));
    }
  };

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center animate-fade-in">
      {/* Hero */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-50 dark:bg-brand-900/20 text-brand-600 dark:text-brand-400 text-sm font-medium mb-4">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Lead Discovery Engine
        </div>
        <h1 className="text-5xl font-bold text-gray-900 dark:text-white mb-4">
          Discover Any Buyer,<br />
          <span className="bg-gradient-to-r from-brand-500 to-purple-600 bg-clip-text text-transparent">
            Anywhere in India
          </span>
        </h1>
        <p className="text-lg text-gray-500 dark:text-gray-400 max-w-xl mx-auto">
          AI-powered search engine for business discovery. Enter any product, industry, or service
          to automatically find thousands of companies across India.
        </p>
      </div>

      {/* Search Bar */}
      <div className="w-full max-w-2xl mb-6">
        <form onSubmit={handleSubmit}>
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder='e.g. "Palm Oil Buyers India" or "Restaurants Hyderabad"'
              className="w-full px-6 py-4 pl-14 pr-36 rounded-2xl border-2 border-gray-200 dark:border-dark-600 bg-white dark:bg-dark-800 text-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-500 focus:border-brand-500 shadow-lg"
              disabled={loading}
            />
            <svg className="w-6 h-6 text-gray-400 absolute left-5 top-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            {loading && (
              <div className="absolute right-5 top-4">
                <svg className="w-6 h-6 animate-spin text-brand-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            )}
          </div>

          {/* Mode Toggle */}
          <div className="flex items-center gap-2 mt-3 mb-2">
            <button
              type="button"
              onClick={() => setMode("pipeline")}
              className={`text-xs px-3 py-1.5 rounded-full transition-all ${
                mode === "pipeline"
                  ? "bg-brand-600 text-white"
                  : "bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-400"
              }`}
            >
              Full Discovery
            </button>
            <button
              type="button"
              onClick={() => setMode("quick")}
              className={`text-xs px-3 py-1.5 rounded-full transition-all ${
                mode === "quick"
                  ? "bg-brand-600 text-white"
                  : "bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-400"
              }`}
            >
              Quick Search
            </button>
            <span className="text-xs text-gray-400 ml-2">
              {mode === "pipeline"
                ? "Expands query into 500+ variations, crawls all sources, enriches, verifies & scores"
                : "Searches existing database only"}
            </span>
          </div>

          <div className="flex gap-3 mt-3">
            <button
              type="submit"
              disabled={!query.trim() || loading}
              className="flex-1 btn-primary justify-center disabled:opacity-50 py-3"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {mode === "pipeline" ? "Starting Discovery..." : "Searching..."}
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  {mode === "pipeline" ? "Start Lead Discovery" : "Quick Search"}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={handlePreview}
              disabled={!query.trim() || loading}
              className="btn-secondary disabled:opacity-50"
            >
              Preview Queries
            </button>
          </div>
        </form>
      </div>

      {/* Quick Suggestions */}
      <div className="w-full max-w-2xl mb-8">
        <p className="text-sm text-gray-400 mb-3 text-center">Try searching for:</p>
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s.text}
              onClick={() => { setQuery(s.text); setShowPreview(false); }}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 text-sm text-gray-600 dark:text-gray-400 hover:border-brand-300 hover:text-brand-600 transition-all shadow-sm"
            >
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700 text-gray-500">
                {s.category}
              </span>
              {s.text}
            </button>
          ))}
        </div>
      </div>

      {/* Query Preview */}
      {showPreview && preview && (
        <div className="w-full max-w-4xl mb-6">
          <div className="glass-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 dark:text-white">
                Search Plan: {preview.total_variations} variations
                <span className="ml-2 text-sm font-normal text-gray-500">
                  (type: {preview.query_type})
                </span>
              </h3>
              <button onClick={() => setShowPreview(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            {preview.by_source && (
              <div className="flex flex-wrap gap-2 mb-3">
                {Object.entries(preview.by_source).map(([source, count]) => (
                  <span key={source} className="text-xs px-2.5 py-1 rounded-full bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-300 font-medium">
                    {source}: {count}
                  </span>
                ))}
              </div>
            )}
            <div className="text-sm text-gray-500 mb-3">
              Locations covered: {preview.locations_covered}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-[300px] overflow-y-auto">
              {preview.variations?.map((v, i) => (
                <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 dark:bg-dark-700 text-sm">
                  <span className="w-5 h-5 rounded-full bg-brand-100 dark:bg-brand-900/30 text-brand-600 text-xs flex items-center justify-center shrink-0">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-700 dark:text-gray-300 truncate">{v.query}</p>
                    <p className="text-xs text-gray-400">{v.source} &middot; {v.location || "India"}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Quick Results */}
      {quickResults && (
        <div className="w-full max-w-4xl">
          <div className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 dark:text-white">
                Quick Search Results ({quickResults.total} found)
              </h3>
              <button onClick={() => setQuickResults(null)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {quickResults.results.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-400 mb-3">No results in database.</p>
                <button
                  onClick={handleFullDiscovery}
                  className="btn-primary"
                >
                  Start Lead Discovery
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {quickResults.results.map((company) => (
                  <div
                    key={company.id}
                    onClick={() => navigate(`/company/${company.id}`)}
                    className="flex items-center gap-4 p-3 rounded-xl hover:bg-gray-50 dark:hover:bg-dark-700 cursor-pointer transition-colors"
                  >
                    <div className="w-10 h-10 rounded-lg bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center text-brand-600 font-bold text-sm shrink-0">
                      {company.company_name?.charAt(0) || "?"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 dark:text-white truncate">
                        {company.company_name}
                      </p>
                      <p className="text-sm text-gray-500 truncate">
                        {company.industry || "Unknown"} &middot; {company.city || ""} {company.state || ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {company.lead_score > 0 && (
                        <span className={`text-xs px-2 py-1 rounded-full ${
                          company.lead_score >= 70 ? "bg-green-100 text-green-700" :
                          company.lead_score >= 40 ? "bg-yellow-100 text-yellow-700" :
                          "bg-gray-100 text-gray-600"
                        }`}>
                          {company.lead_score}
                        </span>
                      )}
                      {company.email && (
                        <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      )}
                      {company.phone && (
                        <svg className="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                        </svg>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Features */}
      <div className="w-full max-w-4xl mt-12 grid grid-cols-1 md:grid-cols-3 gap-5">
        {[
          { title: "10+ Sources", desc: "IndiaMART, TradeIndia, JustDial, Yellow Pages, ExportersIndia — all searched automatically", color: "from-blue-500 to-indigo-600" },
          { title: "AI Query Expansion", desc: "Every search generates 500+ intelligent variations across products, industries, locations", color: "from-purple-500 to-pink-600" },
          { title: "Live Pipeline", desc: "Watch companies get discovered, verified, enriched, and scored in real-time", color: "from-green-500 to-emerald-600" },
        ].map((f) => (
          <div key={f.title} className="glass-card p-5 text-center">
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${f.color} flex items-center justify-center mx-auto mb-3`}>
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-1">{f.title}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">{f.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

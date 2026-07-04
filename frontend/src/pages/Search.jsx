import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { globalSearch, startPipeline } from "../api/client";

const SUGGESTIONS = [
  { text: "Palm Oil Buyers India", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" },
  { text: "Food Manufacturers Karnataka", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" },
  { text: "Edible Oil Distributors Mumbai", icon: "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" },
  { text: "Soap Manufacturers Gujarat", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" },
  { text: "CP10 Importers India", icon: "M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z" },
  { text: "Bakery Manufacturers Delhi", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" },
];

export default function Search() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [quickResults, setQuickResults] = useState(null);

  const handleQuickSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await globalSearch({ q: query.trim(), limit: 20 });
      setQuickResults(res.data);
    } catch (err) {
      console.error("Search error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleFullDiscovery = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await startPipeline({
        query: query.trim(),
        max_queries: 50,
        max_pages_per_spider: 3,
      });
      navigate("/discovery", { state: { runId: res.data.run_id, query: query.trim() } });
    } catch (err) {
      console.error("Pipeline error:", err);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center animate-fade-in">
      {/* Hero */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-50 dark:bg-brand-900/20 text-brand-600 dark:text-brand-400 text-sm font-medium mb-4">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          BuyerHunter AI
        </div>
        <h1 className="text-5xl font-bold text-gray-900 dark:text-white mb-4">
          Find Any Buyer,<br />
          <span className="bg-gradient-to-r from-brand-500 to-purple-600 bg-clip-text text-transparent">
            Anywhere in India
          </span>
        </h1>
        <p className="text-lg text-gray-500 dark:text-gray-400 max-w-xl mx-auto">
          Search across 10+ business directories, government sources, and company websites.
          Get verified contacts, AI-scored leads, and buyer intelligence.
        </p>
      </div>

      {/* Search Bar */}
      <div className="w-full max-w-2xl mb-6">
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleQuickSearch()}
            placeholder='Search for any product, industry, or company...'
            className="w-full px-6 py-4 pl-14 rounded-2xl border-2 border-gray-200 dark:border-dark-600 bg-white dark:bg-dark-800 text-lg text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-500 focus:border-brand-500 shadow-lg"
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

        <div className="flex gap-3 mt-4">
          <button
            onClick={handleQuickSearch}
            disabled={!query.trim() || loading}
            className="flex-1 btn-secondary justify-center disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            Quick Search
          </button>
          <button
            onClick={handleFullDiscovery}
            disabled={!query.trim() || loading}
            className="flex-1 btn-primary justify-center disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Full Discovery Pipeline
          </button>
        </div>
      </div>

      {/* Quick Suggestions */}
      <div className="w-full max-w-2xl mb-10">
        <p className="text-sm text-gray-400 mb-3 text-center">Try searching for:</p>
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s.text}
              onClick={() => { setQuery(s.text); }}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 text-sm text-gray-600 dark:text-gray-400 hover:border-brand-300 hover:text-brand-600 transition-all shadow-sm"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={s.icon} />
              </svg>
              {s.text}
            </button>
          ))}
        </div>
      </div>

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
              <p className="text-center text-gray-400 py-8">
                No results found. Try the Full Discovery Pipeline to search across multiple sources.
              </p>
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
                        {company.industry || "Unknown Industry"} &middot; {company.city || ""} {company.state || ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {company.lead_score > 0 && (
                        <span className={`text-xs px-2 py-1 rounded-full ${
                          company.lead_score >= 70 ? "bg-green-100 text-green-700" :
                          company.lead_score >= 40 ? "bg-yellow-100 text-yellow-700" :
                          "bg-gray-100 text-gray-600"
                        }`}>
                          Score: {company.lead_score}
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
          { title: "10+ Sources", desc: "IndiaMART, JustDial, TradeIndia, Yellow Pages, Government directories, and more", color: "from-blue-500 to-indigo-600" },
          { title: "AI Scoring", desc: "Every lead is scored for buying potential, palm oil relevance, and procurement maturity", color: "from-purple-500 to-pink-600" },
          { title: "Verified Data", desc: "Cross-checked across multiple public sources with confidence scores on every record", color: "from-green-500 to-emerald-600" },
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

import { useState, useEffect } from "react";
import { importApeda, importDgcis, startCrawl, getSpiders, getCrawlLogs, getCrawlStatus } from "../api/client";

const SOURCE_CARDS = [
  {
    id: "apeda",
    name: "APEDA",
    description: "Agricultural & Processed Food Products Export Development Authority. Government directory of registered food exporters.",
    type: "government",
    color: "from-blue-500 to-blue-700",
    icon: "M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z",
    action: "apeda",
  },
  {
    id: "dgcis",
    name: "DGCIS",
    description: "Directorate General of Foreign Trade. India's official import/export trade statistics and buyer data.",
    type: "government",
    color: "from-green-500 to-emerald-700",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    action: "dgcis",
  },
  {
    id: "indiamart",
    name: "IndiaMART",
    description: "India's largest B2B marketplace. Discovers edible oil buyers, distributors, and manufacturers.",
    type: "directory",
    color: "from-orange-500 to-red-600",
    icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
    action: "indiamart",
  },
  {
    id: "tradeindia",
    name: "TradeIndia",
    description: "B2B trade portal connecting Indian manufacturers with global buyers.",
    type: "directory",
    color: "from-purple-500 to-indigo-600",
    icon: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9",
    action: "tradeindia",
  },
  {
    id: "exportersindia",
    name: "ExportersIndia",
    description: "Export and import directory for Indian exporters and international buyers.",
    type: "directory",
    color: "from-teal-500 to-cyan-600",
    icon: "M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z",
    action: "exportersindia",
  },
  {
    id: "googlemaps",
    name: "Google Maps",
    description: "Discover local food businesses, restaurants, and manufacturers via Google Maps.",
    type: "maps",
    color: "from-yellow-500 to-orange-500",
    icon: "M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z",
    action: "googlemaps",
  },
  {
    id: "gst_directory",
    name: "GST Portal",
    description: "Government GST registration directory. Find registered food businesses by GST number.",
    type: "government",
    color: "from-red-500 to-pink-600",
    icon: "M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z",
    action: "gst_directory",
  },
  {
    id: "companywebsite",
    name: "Company Websites",
    description: "Crawl individual company websites to extract contact information and business details.",
    type: "website",
    color: "from-indigo-500 to-purple-600",
    icon: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9",
    action: "companywebsite",
  },
  {
    id: "justdial",
    name: "JustDial",
    description: "Local business directory. Find food retailers, restaurants, and distributors near you.",
    type: "directory",
    color: "from-pink-500 to-rose-600",
    icon: "M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z",
    action: "justdial",
  },
  {
    id: "linkedin",
    name: "LinkedIn",
    description: "Professional network. Find procurement managers and decision makers at food companies.",
    type: "social",
    color: "from-blue-600 to-blue-800",
    icon: "M16 8a6 6 0 01-12 0 6 6 0 0112 0zM2 21a8 8 0 0116 0M16 8v13",
    action: "linkedin",
  },
  {
    id: "yellowpages",
    name: "Yellow Pages",
    description: "Business directory with company listings, contact details, and reviews.",
    type: "directory",
    color: "from-yellow-400 to-yellow-600",
    icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
    action: "yellowpages",
  },
];

const TYPE_COLORS = {
  government: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  directory: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  maps: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  website: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  social: "bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400",
};

function SourceCard({ source, onRun, running }) {
  return (
    <div className="bg-white dark:bg-dark-800 rounded-xl border border-gray-200 dark:border-dark-700 p-5 hover:shadow-lg transition-all group">
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${source.color} flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform`}>
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={source.icon} />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-gray-900 dark:text-white">{source.name}</h3>
            <span className={`px-2 py-0.5 text-xs rounded-full ${TYPE_COLORS[source.type]}`}>{source.type}</span>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2">{source.description}</p>
        </div>
      </div>
      <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100 dark:border-dark-700">
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-gray-300"></div>
            Idle
          </span>
        </div>
        <button
          onClick={() => onRun(source.action)}
          disabled={running}
          className="px-4 py-1.5 text-sm font-medium text-white bg-gradient-to-r from-brand-500 to-brand-600 rounded-lg hover:from-brand-600 hover:to-brand-700 disabled:opacity-50 transition-all"
        >
          {running === source.action ? (
            <span className="flex items-center gap-2">
              <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-white"></div>
              Running...
            </span>
          ) : (
            "Run Now"
          )}
        </button>
      </div>
    </div>
  );
}

export default function CrawlHistory() {
  const [importing, setImporting] = useState("");
  const [importMsg, setImportMsg] = useState("");
  const [spiders, setSpiders] = useState({});
  const [crawlLogs, setCrawlLogs] = useState([]);
  const [crawlStatus, setCrawlStatus] = useState({ running: [], interrupted: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getSpiders(), getCrawlLogs({ limit: 10 }), getCrawlStatus()])
      .then(([s, logs, status]) => {
        setSpiders(s.data.spiders || {});
        setCrawlLogs(logs.data || []);
        setCrawlStatus(status.data || { running: [], interrupted: [] });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleRunSource = async (sourceId) => {
    setImporting(sourceId);
    setImportMsg("");
    try {
      if (sourceId === "apeda") {
        const res = await importApeda({});
        setImportMsg(res.data.message || "APEDA import started");
      } else if (sourceId === "dgcis") {
        const res = await importDgcis({ hs_code: "1511", all_years: true });
        setImportMsg(res.data.message || "DGCIS import started");
      } else {
        const res = await startCrawl({ spider_name: sourceId, keywords: [], max_pages: 3 });
        setImportMsg(res.data.message || `${sourceId} crawl started`);
      }
    } catch (err) {
      setImportMsg(`Failed to start ${sourceId}`);
    } finally {
      setImporting("");
      setTimeout(() => setImportMsg(""), 5000);
    }
  };

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Source Manager</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Manage data sources and run crawlers</p>
        </div>
        <div className="flex items-center gap-3">
          {crawlStatus.running.length > 0 && (
            <span className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
              {crawlStatus.running.length} running
            </span>
          )}
        </div>
      </div>

      {/* Status Message */}
      {importMsg && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3 text-sm text-green-700 dark:text-green-400">
          {importMsg}
        </div>
      )}

      {/* Source Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {SOURCE_CARDS.map((source) => (
          <SourceCard
            key={source.id}
            source={source}
            onRun={handleRunSource}
            running={importing}
          />
        ))}
      </div>

      {/* Recent Crawl Logs */}
      <div className="glass-card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-200 dark:border-dark-700">
          <h2 className="font-semibold text-gray-900 dark:text-white">Recent Crawl Logs</h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading logs...</div>
        ) : crawlLogs.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <p>No crawl logs yet. Run a source to get started.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-dark-700">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Spider</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Started</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Finished</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase">Errors</th>
                </tr>
              </thead>
              <tbody>
                {crawlLogs.map((log) => (
                  <tr key={log.id} className="border-b border-gray-50 dark:border-dark-700/50 hover:bg-gray-50 dark:hover:bg-dark-800/50">
                    <td className="px-5 py-3 text-sm font-medium text-gray-900 dark:text-white capitalize">{log.spider_name}</td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full font-medium ${
                        log.status === "completed" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" :
                        log.status === "running" ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400" :
                        log.status === "failed" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" :
                        "bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-gray-400"
                      }`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${
                          log.status === "completed" ? "bg-green-500" :
                          log.status === "running" ? "bg-yellow-500 animate-pulse" :
                          log.status === "failed" ? "bg-red-500" : "bg-gray-400"
                        }`}></div>
                        {log.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-xs text-gray-500">{log.start_time ? new Date(log.start_time).toLocaleString() : "-"}</td>
                    <td className="px-5 py-3 text-xs text-gray-500">{log.end_time ? new Date(log.end_time).toLocaleString() : "-"}</td>
                    <td className="px-5 py-3 text-xs text-gray-500">{log.errors || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

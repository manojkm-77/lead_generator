import { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { getCompanies, getStats, exportLeads } from "../api/client";

function ScoreBadge({ score }) {
  let color = "bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-gray-400";
  let barColor = "bg-gray-400";
  if (score >= 70) { color = "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"; barColor = "bg-green-500"; }
  else if (score >= 40) { color = "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"; barColor = "bg-yellow-500"; }
  else if (score >= 20) { color = "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"; barColor = "bg-orange-500"; }
  return (
    <div className="flex items-center gap-2">
      <div className="w-14 bg-gray-200 dark:bg-dark-700 rounded-full h-1.5">
        <div className={`${barColor} h-1.5 rounded-full`} style={{ width: `${score}%` }}></div>
      </div>
      <span className={`badge ${color}`}>{score}</span>
    </div>
  );
}

function ContactPill({ type, value }) {
  if (!value) return <span className="text-gray-300 dark:text-dark-600">-</span>;
  const icons = {
    email: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    phone: "M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z",
    website: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9",
  };
  return (
    <div className="flex items-center gap-1 text-sm text-gray-600 dark:text-gray-400">
      <svg className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icons[type]} />
      </svg>
      <span className="truncate max-w-[140px]">{value}</span>
    </div>
  );
}

function FilterChip({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium rounded-full border transition-colors ${
        active
          ? "bg-brand-50 text-brand-700 border-brand-300 dark:bg-brand-900/30 dark:text-brand-400 dark:border-brand-700"
          : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50 dark:bg-dark-800 dark:text-gray-400 dark:border-dark-700 dark:hover:bg-dark-700"
      }`}
    >
      {label}
    </button>
  );
}

export default function Companies() {
  const [companies, setCompanies] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({});
  const [selected, setSelected] = useState([]);
  const [showFilters, setShowFilters] = useState(false);
  const [pageSize] = useState(20);
  const [lastRefreshed, setLastRefreshed] = useState(null);
  const [activeCrawlers, setActiveCrawlers] = useState(0);
  const pollRef = useRef(null);

  const fetchCompanies = useCallback(() => {
    setLoading(true);
    const params = { page, page_size: pageSize, search, ...filters };
    Object.keys(params).forEach((k) => {
      if (params[k] === "" || params[k] === null || params[k] === undefined) delete params[k];
    });
    Promise.all([
      getCompanies(params),
      getStats().catch(() => ({ data: { active_crawlers: 0 } })),
    ])
      .then(([cr, sr]) => {
        setCompanies(cr.data.companies);
        setTotal(cr.data.total);
        setActiveCrawlers(sr.data?.active_crawlers || 0);
        setLastRefreshed(new Date());
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, search, filters, pageSize]);

  useEffect(() => { fetchCompanies(); }, [fetchCompanies]);

  // Auto-poll every 15s when there may be new crawl data
  useEffect(() => {
    pollRef.current = setInterval(() => {
      getStats()
        .then((sr) => {
          const ac = sr.data?.active_crawlers || 0;
          setActiveCrawlers(ac);
          if (ac > 0) fetchCompanies();
        })
        .catch(() => {});
    }, 15000);
    return () => clearInterval(pollRef.current);
  }, [fetchCompanies]);

  const handleSearch = (e) => {
    setSearch(e.target.value);
    setPage(1);
  };

  const toggleFilter = (key, value) => {
    setFilters((prev) => {
      const next = { ...prev };
      if (next[key] === value) { delete next[key]; }
      else { next[key] = value; }
      return next;
    });
    setPage(1);
  };

  const setFilter = (key, value) => {
    setFilters((prev) => {
      const next = { ...prev };
      if (!value) delete next[key]; else next[key] = value;
      return next;
    });
    setPage(1);
  };

  const clearFilters = () => {
    setFilters({});
    setSearch("");
    setPage(1);
  };

  const activeFilterCount = Object.keys(filters).length + (search ? 1 : 0);

  const handleExport = async (format) => {
    try {
      const params = { search, ...filters };
      Object.keys(params).forEach((k) => {
        if (params[k] === "" || params[k] === null || params[k] === undefined) delete params[k];
      });
      const resp = await exportLeads(format, params);
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `companies.${format === "excel" ? "xlsx" : "csv"}`;
      a.click();
    } catch (err) {
      alert("Export failed");
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Companies</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">{total.toLocaleString()} companies across all sources</p>
        </div>
        <div className="flex items-center gap-3">
          {activeCrawlers > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-green-600 bg-green-50 dark:bg-green-900/20 dark:text-green-400 px-2.5 py-1 rounded-full">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              {activeCrawlers} active
            </span>
          )}
          {lastRefreshed && (
            <span className="text-xs text-gray-400 hidden lg:block">
              Updated {lastRefreshed.toLocaleTimeString()}
            </span>
          )}
          <button onClick={fetchCompanies} disabled={loading} className="btn-secondary text-sm px-3" title="Refresh">
            <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button onClick={() => handleExport("csv")} className="btn-secondary text-sm">
            <span className="flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              CSV
            </span>
          </button>
          <button onClick={() => handleExport("excel")} className="btn-secondary text-sm">
            <span className="flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Excel
            </span>
          </button>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="glass-card p-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="flex-1 relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search by company, product, email, phone, GST, website..."
              value={search}
              onChange={handleSearch}
              className="input pl-9 text-sm"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-2 text-sm rounded-lg border transition-colors ${
              showFilters || activeFilterCount > 0
                ? "bg-brand-50 text-brand-700 border-brand-300 dark:bg-brand-900/30 dark:text-brand-400"
                : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50 dark:bg-dark-800 dark:text-gray-400 dark:border-dark-700"
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
            Filters {activeFilterCount > 0 && `(${activeFilterCount})`}
          </button>
          {activeFilterCount > 0 && (
            <button onClick={clearFilters} className="text-xs text-gray-500 hover:text-red-500">
              Clear all
            </button>
          )}
        </div>

        {/* Advanced Filters */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-gray-100 dark:border-dark-700 space-y-3">
            <div className="flex flex-wrap gap-2">
              <span className="text-xs font-medium text-gray-500 self-center mr-1">Industry:</span>
              {["Food Manufacturer", "Distributor", "Wholesaler", "Bakery", "Restaurant", "Hotel", "Retail Chain", "Importer", "Exporter"].map((ind) => (
                <FilterChip key={ind} label={ind} active={filters.industry === ind} onClick={() => toggleFilter("industry", ind)} />
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="text-xs font-medium text-gray-500 self-center mr-1">Source:</span>
              {["apeda", "companywebsite", "indiamart", "googlemaps", "exportersindia", "gst_directory"].map((src) => (
                <FilterChip key={src} label={src} active={filters.source === src} onClick={() => toggleFilter("source", src)} />
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs font-medium text-gray-500">Score:</span>
              <input
                type="number"
                placeholder="Min"
                className="input w-20 text-xs py-1"
                value={filters.min_score || ""}
                onChange={(e) => setFilter("min_score", e.target.value)}
              />
              <span className="text-xs text-gray-400">to</span>
              <input
                type="number"
                placeholder="Max"
                className="input w-20 text-xs py-1"
                value={filters.max_score || ""}
                onChange={(e) => setFilter("max_score", e.target.value)}
              />
              <div className="flex items-center gap-4 ml-4">
                <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                  <input type="checkbox" checked={!!filters.has_email} onChange={() => toggleFilter("has_email", true)} className="rounded border-gray-300" />
                  Has Email
                </label>
                <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                  <input type="checkbox" checked={!!filters.has_phone} onChange={() => toggleFilter("has_phone", true)} className="rounded border-gray-300" />
                  Has Phone
                </label>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 dark:border-dark-700 bg-gray-50/50 dark:bg-dark-800/50">
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Company</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Industry</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Products</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Contact</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Location</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Score</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Source</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array(5).fill(0).map((_, i) => (
                  <tr key={i} className="border-b border-gray-100 dark:border-dark-700/50">
                    <td colSpan="8" className="px-5 py-4">
                      <div className="animate-pulse flex space-x-4">
                        <div className="h-4 bg-gray-200 dark:bg-dark-700 rounded w-1/4"></div>
                        <div className="h-4 bg-gray-200 dark:bg-dark-700 rounded w-1/6"></div>
                        <div className="h-4 bg-gray-200 dark:bg-dark-700 rounded w-1/8"></div>
                      </div>
                    </td>
                  </tr>
                ))
              ) : companies.length === 0 ? (
                <tr>
                  <td colSpan="8" className="px-5 py-12 text-center text-gray-500">
                    <div className="flex flex-col items-center">
                      <svg className="w-12 h-12 text-gray-300 dark:text-dark-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                      </svg>
                      <p className="font-medium">No companies found</p>
                      <p className="text-sm text-gray-400 mt-1">Try adjusting your search or filters</p>
                    </div>
                  </td>
                </tr>
              ) : (
                companies.map((c) => (
                  <tr key={c.id} className="table-row border-b border-gray-100 dark:border-dark-700/50">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                          {c.company_name?.charAt(0) || "?"}
                        </div>
                        <div>
                          <Link to={`/company/${c.id}`} className="font-medium text-gray-900 dark:text-white hover:text-brand-600 dark:hover:text-brand-400 text-sm">
                            {c.company_name}
                          </Link>
                          {c.website && (
                            <p className="text-xs text-gray-400 truncate max-w-[180px]">{c.website.replace(/https?:\/\//, "")}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span className="badge badge-info text-xs">{c.industry || "Unknown"}</span>
                    </td>
                    <td className="px-5 py-3">
                      <p className="text-xs text-gray-600 dark:text-gray-400 truncate max-w-[150px]">
                        {c.products || "-"}
                      </p>
                    </td>
                    <td className="px-5 py-3 space-y-0.5">
                      <ContactPill type="email" value={c.email} />
                      <ContactPill type="phone" value={c.phone} />
                    </td>
                    <td className="px-5 py-3 text-xs text-gray-600 dark:text-gray-400">
                      {c.city || "-"}
                      {c.state ? `, ${c.state}` : ""}
                    </td>
                    <td className="px-5 py-3">
                      <ScoreBadge score={c.lead_score || 0} />
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-xs text-gray-500 capitalize">{c.source || "-"}</span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1">
                        <Link to={`/company/${c.id}`} className="text-xs text-brand-600 hover:text-brand-700 font-medium px-2 py-1 rounded hover:bg-brand-50 dark:hover:bg-brand-900/20">
                          View
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-gray-200 dark:border-dark-700 bg-gray-50/50 dark:bg-dark-800/30">
            <p className="text-xs text-gray-500">
              Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, total)} of {total.toLocaleString()}
            </p>
            <div className="flex items-center gap-1">
              <button
                disabled={page <= 1}
                onClick={() => setPage(1)}
                className="px-2 py-1 text-xs border border-gray-200 dark:border-dark-700 rounded disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-dark-700"
              >
                First
              </button>
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-2 py-1 text-xs border border-gray-200 dark:border-dark-700 rounded disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-dark-700"
              >
                Prev
              </button>
              <span className="px-3 py-1 text-xs text-gray-500">
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="px-2 py-1 text-xs border border-gray-200 dark:border-dark-700 rounded disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-dark-700"
              >
                Next
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(totalPages)}
                className="px-2 py-1 text-xs border border-gray-200 dark:border-dark-700 rounded disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-dark-700"
              >
                Last
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

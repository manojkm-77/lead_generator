import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { getProcurementContacts } from "../api/intelligence";

function ConfidenceBadge({ score }) {
  let color = "bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-gray-400";
  if (score >= 70) color = "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
  else if (score >= 40) color = "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-12 bg-gray-200 dark:bg-dark-700 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${score >= 70 ? "bg-green-500" : score >= 40 ? "bg-yellow-500" : "bg-gray-400"}`} style={{ width: `${score}%` }}></div>
      </div>
      <span className={`text-xs font-medium ${color}`}>{score}%</span>
    </div>
  );
}

function ContactAvatar({ name }) {
  const initials = name ? name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase() : "??";
  const colors = [
    "from-blue-500 to-blue-700",
    "from-green-500 to-green-700",
    "from-purple-500 to-purple-700",
    "from-orange-500 to-orange-700",
    "from-pink-500 to-pink-700",
    "from-teal-500 to-teal-700",
  ];
  const colorIndex = name ? name.charCodeAt(0) % colors.length : 0;
  return (
    <div className={`w-9 h-9 rounded-full bg-gradient-to-br ${colors[colorIndex]} flex items-center justify-center text-white text-xs font-bold flex-shrink-0`}>
      {initials}
    </div>
  );
}

export default function ProcurementContacts() {
  const [contacts, setContacts] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState([]);

  useEffect(() => {
    setLoading(true);
    getProcurementContacts({ page, page_size: 50 })
      .then((r) => { setContacts(r.data.contacts); setTotal(r.data.total); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page]);

  const toggleSelect = (id) => {
    setSelected((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  };

  const selectAll = () => {
    if (selected.length === contacts.length) setSelected([]);
    else setSelected(contacts.map((c) => c.id));
  };

  const filteredContacts = search
    ? contacts.filter((c) =>
        (c.person_name || "").toLowerCase().includes(search.toLowerCase()) ||
        (c.company_name || "").toLowerCase().includes(search.toLowerCase()) ||
        (c.email || "").toLowerCase().includes(search.toLowerCase()) ||
        (c.designation || "").toLowerCase().includes(search.toLowerCase())
      )
    : contacts;

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Decision Makers</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">{total} procurement contacts discovered</p>
        </div>
        <div className="flex items-center gap-3">
          {selected.length > 0 && (
            <span className="text-sm text-brand-600 dark:text-brand-400">
              {selected.length} selected
            </span>
          )}
          <button className="btn-secondary text-sm">
            <span className="flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export
            </span>
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="glass-card p-4">
        <div className="flex items-center gap-3">
          <div className="flex-1 relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search by name, company, email, or designation..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-9 text-sm"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 dark:border-dark-700 bg-gray-50/50 dark:bg-dark-800/50">
                <th className="w-10 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selected.length === filteredContacts.length && filteredContacts.length > 0}
                    onChange={selectAll}
                    className="rounded border-gray-300"
                  />
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Contact</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Designation</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Company</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Email</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Phone</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Confidence</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Source</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array(5).fill(0).map((_, i) => (
                  <tr key={i} className="border-b border-gray-100 dark:border-dark-700/50">
                    <td colSpan="8" className="px-4 py-4">
                      <div className="animate-pulse flex space-x-4">
                        <div className="h-4 bg-gray-200 dark:bg-dark-700 rounded w-1/4"></div>
                        <div className="h-4 bg-gray-200 dark:bg-dark-700 rounded w-1/6"></div>
                      </div>
                    </td>
                  </tr>
                ))
              ) : filteredContacts.length === 0 ? (
                <tr>
                  <td colSpan="8" className="px-4 py-12 text-center text-gray-500">
                    <div className="flex flex-col items-center">
                      <svg className="w-12 h-12 text-gray-300 dark:text-dark-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <p className="font-medium">No contacts found</p>
                      <p className="text-sm text-gray-400 mt-1">Run intelligence analysis to discover contacts</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredContacts.map((c) => (
                  <tr key={c.id} className="table-row border-b border-gray-100 dark:border-dark-700/50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selected.includes(c.id)}
                        onChange={() => toggleSelect(c.id)}
                        className="rounded border-gray-300"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <ContactAvatar name={c.person_name} />
                        <div>
                          <p className="font-medium text-gray-900 dark:text-white text-sm">{c.person_name}</p>
                          {c.email && <p className="text-xs text-gray-400">{c.email}</p>}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{c.designation || "-"}</td>
                    <td className="px-4 py-3">
                      {c.company_name ? (
                        <Link to={`/intelligence/${c.company_id}`} className="text-sm text-brand-600 hover:text-brand-700 font-medium">
                          {c.company_name}
                        </Link>
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {c.email ? (
                        <a href={`mailto:${c.email}`} className="text-sm text-gray-600 dark:text-gray-400 hover:text-brand-600">
                          {c.email}
                        </a>
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {c.phone ? (
                        <a href={`tel:${c.phone}`} className="text-sm text-gray-600 dark:text-gray-400 hover:text-brand-600">
                          {c.phone}
                        </a>
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <ConfidenceBadge score={c.confidence_score || 0} />
                    </td>
                    <td className="px-4 py-3">
                      {c.source_url ? (
                        <a href={c.source_url} target="_blank" rel="noreferrer" className="text-xs text-brand-600 hover:underline">
                          View
                        </a>
                      ) : (
                        <span className="text-xs text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 50 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-gray-200 dark:border-dark-700">
            <p className="text-xs text-gray-500">
              Showing {((page - 1) * 50) + 1} to {Math.min(page * 50, total)} of {total}
            </p>
            <div className="flex items-center gap-1">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-2 py-1 text-xs border border-gray-200 dark:border-dark-700 rounded disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-dark-700">Prev</button>
              <span className="px-3 py-1 text-xs text-gray-500">{page} / {Math.ceil(total / 50)}</span>
              <button disabled={page * 50 >= total} onClick={() => setPage(page + 1)} className="px-2 py-1 text-xs border border-gray-200 dark:border-dark-700 rounded disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-dark-700">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

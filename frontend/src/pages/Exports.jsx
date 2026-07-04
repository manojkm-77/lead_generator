import { useState, useEffect } from "react";
import { getCompanies, exportLeads } from "../api/client";

const EXPORT_FORMATS = [
  { id: "csv", label: "CSV", description: "Comma-separated values, compatible with all spreadsheets", icon: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  { id: "excel", label: "Excel", description: "Microsoft Excel format with formatting", icon: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  { id: "json", label: "JSON", description: "Structured data format for APIs and integrations", icon: "M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" },
];

const PRESETS = [
  { id: "all", label: "All Companies", description: "Export entire database", filter: {} },
  { id: "high-score", label: "High Score Buyers", description: "Score >= 70", filter: { min_score: 70 } },
  { id: "with-email", label: "With Email", description: "Companies with email addresses", filter: { has_email: true } },
  { id: "with-phone", label: "With Phone", description: "Companies with phone numbers", filter: { has_phone: true } },
  { id: "importers", label: "Importers", description: "All importing companies", filter: { source: "apeda" } },
];

export default function Exports() {
  const [selectedFormat, setSelectedFormat] = useState("csv");
  const [selectedPreset, setSelectedPreset] = useState("all");
  const [exporting, setExporting] = useState(false);
  const [exportMsg, setExportMsg] = useState("");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCompanies({ page: 1, page_size: 1 })
      .then((r) => setStats({ total: r.data.total }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleExport = async () => {
    setExporting(true);
    setExportMsg("");
    try {
      const preset = PRESETS.find((p) => p.id === selectedPreset);
      const params = { ...preset.filter, limit: 10000 };
      const resp = await exportLeads(selectedFormat, params);

      const blob = new Blob([resp.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ext = selectedFormat === "excel" ? "xlsx" : selectedFormat;
      a.download = `buyerhunter_export_${new Date().toISOString().slice(0, 10)}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      setExportMsg(`Exported successfully! ${resp.data.count || "Check downloads."}`);
    } catch (err) {
      setExportMsg("Export failed. Please try again.");
    } finally {
      setExporting(false);
      setTimeout(() => setExportMsg(""), 5000);
    }
  };

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Export Data</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          Export your buyer intelligence data in multiple formats
        </p>
      </div>

      {/* Export Stats */}
      {!loading && stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="glass-card p-5">
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Companies</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{stats.total.toLocaleString()}</p>
          </div>
          <div className="glass-card p-5">
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Selected Preset</p>
            <p className="text-2xl font-bold text-brand-600 dark:text-brand-400 mt-1">
              {PRESETS.find((p) => p.id === selectedPreset)?.label}
            </p>
          </div>
          <div className="glass-card p-5">
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Format</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1 uppercase">{selectedFormat}</p>
          </div>
        </div>
      )}

      {/* Export Message */}
      {exportMsg && (
        <div className={`p-3 rounded-lg text-sm ${
          exportMsg.includes("failed")
            ? "bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400"
            : "bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400"
        }`}>
          {exportMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Format Selection */}
        <div className="glass-card p-6">
          <h2 className="font-semibold text-gray-900 dark:text-white mb-4">Export Format</h2>
          <div className="space-y-3">
            {EXPORT_FORMATS.map((fmt) => (
              <label
                key={fmt.id}
                className={`flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                  selectedFormat === fmt.id
                    ? "border-brand-500 bg-brand-50 dark:bg-brand-900/20"
                    : "border-gray-200 dark:border-dark-700 hover:border-gray-300 dark:hover:border-dark-600"
                }`}
              >
                <input
                  type="radio"
                  name="format"
                  value={fmt.id}
                  checked={selectedFormat === fmt.id}
                  onChange={(e) => setSelectedFormat(e.target.value)}
                  className="text-brand-600 focus:ring-brand-500"
                />
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  selectedFormat === fmt.id ? "bg-brand-500" : "bg-gray-100 dark:bg-dark-700"
                }`}>
                  <svg className={`w-5 h-5 ${selectedFormat === fmt.id ? "text-white" : "text-gray-500"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={fmt.icon} />
                  </svg>
                </div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">{fmt.label}</p>
                  <p className="text-xs text-gray-500">{fmt.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Preset Selection */}
        <div className="glass-card p-6">
          <h2 className="font-semibold text-gray-900 dark:text-white mb-4">Data Preset</h2>
          <div className="space-y-3">
            {PRESETS.map((preset) => (
              <label
                key={preset.id}
                className={`flex items-center gap-4 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                  selectedPreset === preset.id
                    ? "border-brand-500 bg-brand-50 dark:bg-brand-900/20"
                    : "border-gray-200 dark:border-dark-700 hover:border-gray-300 dark:hover:border-dark-600"
                }`}
              >
                <input
                  type="radio"
                  name="preset"
                  value={preset.id}
                  checked={selectedPreset === preset.id}
                  onChange={(e) => setSelectedPreset(e.target.value)}
                  className="text-brand-600 focus:ring-brand-500"
                />
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">{preset.label}</p>
                  <p className="text-xs text-gray-500">{preset.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Export Button */}
      <div className="flex justify-center">
        <button
          onClick={handleExport}
          disabled={exporting}
          className="px-8 py-3 text-lg font-semibold text-white bg-gradient-to-r from-brand-500 to-brand-600 rounded-xl hover:from-brand-600 hover:to-brand-700 disabled:opacity-50 transition-all shadow-lg shadow-brand-500/25"
        >
          {exporting ? (
            <span className="flex items-center gap-3">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              Exporting...
            </span>
          ) : (
            <span className="flex items-center gap-3">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download Export
            </span>
          )}
        </button>
      </div>
    </div>
  );
}

import { useState, useEffect } from "react";
import { getTradeSummary, getTradeData } from "../api/client";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, Legend, PieChart, Pie, Cell,
  AreaChart, Area,
} from "recharts";

const COLORS = {
  palmOil: "#6366f1",
  palmKernel: "#f59e0b",
  total: "#22c55e",
  grid: "#e2e8f0",
};

function StatCard({ title, value, subtitle, color }) {
  return (
    <div className="glass-card p-5">
      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
      <p className={`text-2xl font-bold mt-1 ${color || "text-gray-900 dark:text-white"}`}>
        {value}
      </p>
      {subtitle && (
        <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
      )}
    </div>
  );
}

function ChartCard({ title, children, subtitle }) {
  return (
    <div className="glass-card p-6">
      <div className="mb-4">
        <h3 className="font-semibold text-gray-900 dark:text-white">{title}</h3>
        {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

const tooltipStyle = {
  backgroundColor: "#1e293b",
  border: "none",
  borderRadius: "8px",
  color: "#f1f5f9",
  fontSize: 13,
};

export default function TradeAnalytics() {
  const [summary, setSummary] = useState([]);
  const [rawData, setRawData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("trend");

  useEffect(() => {
    Promise.all([
      getTradeSummary().catch(() => ({ data: [] })),
      getTradeData().catch(() => ({ data: [] })),
    ]).then(([s, r]) => {
      const summaryData = Array.isArray(s.data) ? s.data : [];
      const rawDataArr = Array.isArray(r.data) ? r.data :
        Array.isArray(r.data?.companies) ? r.data.companies : [];
      setSummary(summaryData);
      setRawData(rawDataArr);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
      </div>
    );
  }

  // Normalize arrays (API may return dict instead of array)
  const safeSummary = Array.isArray(summary) ? summary : [];
  const safeRaw = Array.isArray(rawData) ? rawData : [];

  // Check if we have real trade data
  const hasRealData = safeSummary.some((r) => r && r.total_value > 0);

  if (!hasRealData && safeSummary.length > 0) {
    return (
      <div className="animate-fade-in space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Trade Analytics</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">India palm oil import data from DGCIS</p>
        </div>
        <div className="glass-card p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <p className="text-gray-900 dark:text-white font-semibold text-lg">No Trade Data Yet</p>
          <p className="text-sm text-gray-500 mt-2 max-w-md mx-auto">
            The DGCIS trade data import has been run but the values were not parsed correctly.
            Run the DGCIS import from the Source Manager to fetch real import/export data.
          </p>
          <a href="/crawls" className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-brand-600 rounded-lg hover:bg-brand-700">
            Go to Source Manager
          </a>
        </div>
        <div className="text-xs text-gray-400 dark:text-gray-500">
          Data source: DGCI&S, Kolkata (tradestat.commerce.gov.in). HS 1511 = Crude Palm Oil, HS 1513 = Palm Kernel Oil.
        </div>
      </div>
    );
  }

  // Process data for charts
  const yearMap = {};
  safeSummary.forEach((row) => {
    if (!row || !row.year) return;
    const yr = row.year;
    if (!yearMap[yr]) yearMap[yr] = { year: yr };
    if (row.hs_code === "1511") yearMap[yr].palmOil = row.total_value;
    if (row.hs_code === "1513") yearMap[yr].palmKernel = row.total_value;
  });

  const trendData = Object.values(yearMap)
    .sort((a, b) => (a.year || "").localeCompare(b.year || ""))
    .map((d) => ({
      ...d,
      palmOil: d.palmOil || 0,
      palmKernel: d.palmKernel || 0,
      total: (d.palmOil || 0) + (d.palmKernel || 0),
    }));

  const latestYear = trendData[trendData.length - 1] || {};
  const prevYear = trendData[trendData.length - 2] || {};
  const yoyGrowth = prevYear.total
    ? (((latestYear.total - prevYear.total) / prevYear.total) * 100).toFixed(1)
    : "N/A";
  const peakYear = trendData.reduce(
    (max, d) => (d.total > (max.total || 0) ? d : max),
    {}
  );

  // Country data from raw records (if available)
  const countryMap = {};
  safeRaw.forEach((r) => {
    if (r && r.country && r.value_usd_million > 0) {
      countryMap[r.country] = (countryMap[r.country] || 0) + r.value_usd_million;
    }
  });
  const countryData = Object.entries(countryMap)
    .map(([name, value]) => ({ name, value: Math.round(value * 100) / 100 }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  const tabs = [
    { id: "trend", label: "Import Trend" },
    { id: "compare", label: "Palm vs Kernel" },
    { id: "market", label: "Market Share" },
    { id: "table", label: "Data Table" },
  ];

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Palm Oil Trade Analytics
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          India import data from DGCIS (2017-2026) — HS 1511 &amp; 1513
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Latest Year Imports"
          value={`$${(latestYear.total / 1000 || 0).toFixed(1)}B`}
          subtitle={latestYear.year || "N/A"}
          color="text-brand-600 dark:text-brand-400"
        />
        <StatCard
          title="YoY Growth"
          value={`${yoyGrowth}%`}
          subtitle="vs previous year"
          color={yoyGrowth > 0 ? "text-green-600" : "text-red-600"}
        />
        <StatCard
          title="Peak Year"
          value={`$${(peakYear.total / 1000 || 0).toFixed(1)}B`}
          subtitle={peakYear.year || "N/A"}
          color="text-yellow-600 dark:text-yellow-400"
        />
        <StatCard
          title="8-Year Average"
          value={`$${(trendData.reduce((s, d) => s + d.total, 0) / trendData.length / 1000 || 0).toFixed(1)}B`}
          subtitle={`${trendData.length} years of data`}
          color="text-purple-600 dark:text-purple-400"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-dark-700">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-brand-600 text-brand-600 dark:text-brand-400"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "trend" && (
        <ChartCard title="Palm Oil Import Trend" subtitle="Crude Palm Oil (HS 1511) — US$ Million">
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="colorPalm" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS.palmOil} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={COLORS.palmOil} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
              <XAxis dataKey="year" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}B`} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`$${v.toLocaleString()}M`, "Imports"]} />
              <Area
                type="monotone"
                dataKey="palmOil"
                stroke={COLORS.palmOil}
                strokeWidth={2}
                fill="url(#colorPalm)"
                name="Crude Palm Oil"
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {activeTab === "compare" && (
        <ChartCard title="Crude Palm Oil vs Palm Kernel Oil" subtitle="US$ Million">
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
              <XAxis dataKey="year" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}B`} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`$${v.toLocaleString()}M`]} />
              <Legend />
              <Bar dataKey="palmOil" fill={COLORS.palmOil} name="Crude Palm Oil (1511)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="palmKernel" fill={COLORS.palmKernel} name="Palm Kernel Oil (1513)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {activeTab === "market" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ChartCard title="Market Composition" subtitle="Latest year split">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={[
                    { name: "Crude Palm Oil", value: latestYear.palmOil || 0 },
                    { name: "Palm Kernel Oil", value: latestYear.palmKernel || 0 },
                  ]}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                >
                  <Cell fill={COLORS.palmOil} />
                  <Cell fill={COLORS.palmKernel} />
                </Pie>
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`$${v.toLocaleString()}M`]} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-6 mt-2">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS.palmOil }}></div>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Palm Oil ({((latestYear.palmOil || 0) / (latestYear.total || 1) * 100).toFixed(1)}%)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS.palmKernel }}></div>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Palm Kernel ({((latestYear.palmKernel || 0) / (latestYear.total || 1) * 100).toFixed(1)}%)
                </span>
              </div>
            </div>
          </ChartCard>

          <ChartCard title="Year-over-Year Growth" subtitle="% change in total imports">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={trendData.slice(1).map((d, i) => ({
                year: d.year,
                growth: trendData[i].total
                  ? Number((((d.total - trendData[i].total) / trendData[i].total) * 100).toFixed(1))
                  : 0,
              }))}>
                <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
                <XAxis dataKey="year" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v}%`, "Growth"]} />
                <Bar
                  dataKey="growth"
                  name="YoY Growth %"
                  radius={[4, 4, 0, 0]}
                  fill="#22c55e"
                >
                  {trendData.slice(1).map((entry, idx) => (
                    <Cell key={idx} fill={entry.growth >= 0 || trendData[idx].total === 0 ? "#22c55e" : "#ef4444"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {activeTab === "table" && (
        <ChartCard title="Complete Trade Data">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-dark-700">
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Year</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500">Palm Oil (1511)</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500">Kernel Oil (1513)</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500">Total</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500">YoY Change</th>
                </tr>
              </thead>
              <tbody>
                {trendData.map((row, i) => {
                  const prev = trendData[i - 1];
                  const change = prev && prev.total
                    ? (((row.total - prev.total) / prev.total) * 100).toFixed(1)
                    : null;
                  return (
                    <tr key={row.year} className="border-b border-gray-100 dark:border-dark-800 hover:bg-gray-50 dark:hover:bg-dark-700/50">
                      <td className="py-3 px-4 font-medium text-gray-900 dark:text-white">{row.year}</td>
                      <td className="py-3 px-4 text-right text-gray-700 dark:text-gray-300">
                        ${(row.palmOil || 0).toLocaleString()}M
                      </td>
                      <td className="py-3 px-4 text-right text-gray-700 dark:text-gray-300">
                        ${(row.palmKernel || 0).toLocaleString()}M
                      </td>
                      <td className="py-3 px-4 text-right font-semibold text-gray-900 dark:text-white">
                        ${(row.total || 0).toLocaleString()}M
                      </td>
                      <td className={`py-3 px-4 text-right font-medium ${change > 0 ? "text-green-600" : change < 0 ? "text-red-600" : "text-gray-400"}`}>
                        {change !== null ? `${change > 0 ? "+" : ""}${change}%` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </ChartCard>
      )}

      {/* Source Note */}
      <div className="text-xs text-gray-400 dark:text-gray-500 mt-4">
        Data source: DGCI&S, Kolkata (tradestat.commerce.gov.in). Last updated: May 2026.
        Values in US$ Million. HS 1511 = Crude Palm Oil, HS 1513 = Palm Kernel Oil.
      </div>
    </div>
  );
}

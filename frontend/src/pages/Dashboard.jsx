import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { getStats } from "../api/client";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend,
} from "recharts";

const COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#14b8a6", "#f97316", "#84cc16"];

function StatCard({ title, value, subtitle, icon, color, trend }) {
  return (
    <div className="stat-card group">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{subtitle}</p>}
          {trend !== undefined && (
            <p className={`text-xs mt-1 ${trend >= 0 ? "text-green-600" : "text-red-600"}`}>
              {trend >= 0 ? "+" : ""}{trend}% from last week
            </p>
          )}
        </div>
        <div className={`p-2.5 rounded-xl ${color} group-hover:scale-110 transition-transform`}>
          <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
          </svg>
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, children, action }) {
  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 dark:text-white text-sm">{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );
}

function SkeletonCards() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-8">
      {Array(10).fill(0).map((_, i) => (
        <div key={i} className="stat-card animate-pulse">
          <div className="h-3 bg-gray-200 dark:bg-dark-700 rounded w-20 mb-2"></div>
          <div className="h-7 bg-gray-200 dark:bg-dark-700 rounded w-16 mb-1"></div>
          <div className="h-2 bg-gray-200 dark:bg-dark-700 rounded w-24"></div>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStats()
      .then((r) => setStats(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="animate-fade-in">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
            <p className="text-gray-500 dark:text-gray-400 mt-1">Loading your buyer intelligence overview...</p>
          </div>
        </div>
        <SkeletonCards />
      </div>
    );
  }

  const scoreData = stats?.score_distribution
    ? Object.entries(stats.score_distribution).map(([name, value]) => ({ name, value }))
    : [];
  const industryData = stats?.industry_breakdown
    ? Object.entries(stats.industry_breakdown).slice(0, 8).map(([name, value]) => ({ name, value }))
    : [];
  const sourceData = stats?.source_breakdown
    ? Object.entries(stats.source_breakdown).map(([name, value]) => ({ name, value }))
    : [];
  const stateData = stats?.state_breakdown
    ? Object.entries(stats.state_breakdown).slice(0, 8).map(([name, value]) => ({ name, value }))
    : [];
  const activityData = stats?.recent_activity || [];

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Welcome back. Here's your buyer intelligence overview.</p>
        </div>
        <div className="flex gap-3">
          <Link to="/crawls" className="btn-primary">
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Start Crawl
            </span>
          </Link>
          <Link to="/exports" className="btn-secondary">
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export
            </span>
          </Link>
        </div>
      </div>

      {/* Primary Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <StatCard
          title="Total Companies"
          value={stats?.total_companies || 0}
          subtitle="All sources combined"
          icon="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
          color="bg-gradient-to-br from-brand-500 to-brand-700"
        />
        <StatCard
          title="Verified Buyers"
          value={stats?.verified_buyers || 0}
          subtitle="Score >= 70"
          icon="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          color="bg-gradient-to-br from-green-500 to-emerald-600"
        />
        <StatCard
          title="Verified Emails"
          value={stats?.emails_found || 0}
          subtitle={`${stats?.total_companies ? Math.round((stats.emails_found / stats.total_companies) * 100) : 0}% coverage`}
          icon="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          color="bg-gradient-to-br from-blue-500 to-blue-700"
        />
        <StatCard
          title="Verified Phones"
          value={stats?.phones_found || 0}
          icon="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
          color="bg-gradient-to-br from-purple-500 to-pink-600"
        />
        <StatCard
          title="Active Crawlers"
          value={stats?.active_crawlers || 0}
          subtitle="Running right now"
          icon="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          color="bg-gradient-to-br from-orange-500 to-red-600"
        />
      </div>

      {/* Secondary Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <StatCard title="Importers" value={stats?.importers || 0} icon="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z" color="bg-gradient-to-br from-cyan-500 to-blue-600" />
        <StatCard title="Exporters" value={stats?.exporters || 0} icon="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z" color="bg-gradient-to-br from-teal-500 to-green-600" />
        <StatCard title="Manufacturers" value={stats?.manufacturers || 0} icon="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" color="bg-gradient-to-br from-indigo-500 to-purple-600" />
        <StatCard title="Distributors" value={stats?.distributors || 0} icon="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" color="bg-gradient-to-br from-pink-500 to-rose-600" />
        <StatCard title="Wholesalers" value={stats?.wholesalers || 0} icon="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" color="bg-gradient-to-br from-amber-500 to-orange-600" />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        {/* Lead Growth */}
        <ChartCard title="Lead Growth (Last 14 Days)">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={activityData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "none", borderRadius: "8px", color: "#f1f5f9" }}
              />
              <Line type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Score Distribution */}
        <ChartCard title="Buyer Score Distribution">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={scoreData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "none", borderRadius: "8px", color: "#f1f5f9" }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {scoreData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-5">
        {/* Top Industries */}
        <ChartCard title="Top Industries">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={industryData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={85}
                paddingAngle={3}
                dataKey="value"
              >
                {industryData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "none", borderRadius: "8px", color: "#f1f5f9" }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-2 mt-2">
            {industryData.slice(0, 5).map((item, i) => (
              <div key={item.name} className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }}></div>
                <span className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[100px]">{item.name}</span>
              </div>
            ))}
          </div>
        </ChartCard>

        {/* Top States */}
        <ChartCard title="Top States">
          <div className="space-y-3">
            {stateData.slice(0, 6).map((item, i) => {
              const maxVal = Math.max(...stateData.map(s => s.value));
              const pct = (item.value / maxVal) * 100;
              return (
                <div key={item.name}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{item.name}</span>
                    <span className="text-xs text-gray-500">{item.value}</span>
                  </div>
                  <div className="w-full bg-gray-100 dark:bg-dark-700 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, backgroundColor: COLORS[i % COLORS.length] }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </ChartCard>

        {/* Lead Sources */}
        <ChartCard title="Lead Sources">
          <div className="space-y-3">
            {sourceData.map((item, i) => {
              const maxVal = Math.max(...sourceData.map(s => s.value));
              const pct = (item.value / maxVal) * 100;
              return (
                <div key={item.name}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs font-medium text-gray-700 dark:text-gray-300 capitalize">{item.name}</span>
                    <span className="text-xs text-gray-500">{item.value}</span>
                  </div>
                  <div className="w-full bg-gray-100 dark:bg-dark-700 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, backgroundColor: COLORS[i % COLORS.length] }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </ChartCard>
      </div>

      {/* Quick Actions + Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <ChartCard title="Quick Actions">
          <div className="space-y-2">
            {[
              { to: "/companies", label: "Browse Companies", desc: `${stats?.total_companies || 0} total buyers`, color: "bg-brand-100 dark:bg-brand-900/30", iconColor: "text-brand-600", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" },
              { to: "/crm/intelligence", label: "Buyer Intelligence", desc: "AI-powered analysis", color: "bg-yellow-100 dark:bg-yellow-900/30", iconColor: "text-yellow-600", icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" },
              { to: "/crm/pipeline", label: "Sales Pipeline", desc: "Manage your leads", color: "bg-green-100 dark:bg-green-900/30", iconColor: "text-green-600", icon: "M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" },
              { to: "/crm/contacts", label: "Decision Makers", desc: "Key procurement contacts", color: "bg-purple-100 dark:bg-purple-900/30", iconColor: "text-purple-600", icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" },
              { to: "/analytics", label: "Trade Analytics", desc: "Import/export insights", color: "bg-orange-100 dark:bg-orange-900/30", iconColor: "text-orange-600", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
            ].map((item) => (
              <Link key={item.to} to={item.to} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-50 dark:hover:bg-dark-700 transition-colors">
                <div className={`p-2 ${item.color} rounded-lg`}>
                  <svg className={`w-4 h-4 ${item.iconColor}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} />
                  </svg>
                </div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-white text-sm">{item.label}</p>
                  <p className="text-xs text-gray-500">{item.desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </ChartCard>

        {/* Recent Crawls */}
        <ChartCard title="Recent Crawls">
          <div className="space-y-3">
            {stats?.recent_crawls?.length > 0 ? (
              stats.recent_crawls.map((crawl) => (
                <div key={crawl.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-dark-700">
                  <div className={`w-2 h-2 rounded-full ${
                    crawl.status === "completed" ? "bg-green-500" :
                    crawl.status === "running" ? "bg-yellow-500 animate-pulse" :
                    crawl.status === "failed" ? "bg-red-500" : "bg-gray-400"
                  }`}></div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{crawl.spider_name}</p>
                    <p className="text-xs text-gray-400">{crawl.start_time ? new Date(crawl.start_time).toLocaleString() : "-"}</p>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    crawl.status === "completed" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" :
                    crawl.status === "running" ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400" :
                    crawl.status === "failed" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" :
                    "bg-gray-100 text-gray-600"
                  }`}>{crawl.status}</span>
                </div>
              ))
            ) : (
              <p className="text-center text-gray-400 text-xs py-6">No recent crawls</p>
            )}
          </div>
        </ChartCard>

        {/* Recent Activity */}
        <ChartCard title="Recent Activity">
          <div className="space-y-3">
            {activityData.slice(-5).reverse().map((activity, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className={`w-2 h-2 mt-1.5 rounded-full ${activity.count > 0 ? "bg-green-500" : "bg-gray-300"}`}></div>
                <div>
                  <p className="text-sm text-gray-700 dark:text-gray-300">
                    {activity.count > 0 ? `${activity.count} new companies added` : "No new data"}
                  </p>
                  <p className="text-xs text-gray-400">{activity.date}</p>
                </div>
              </div>
            ))}
            {activityData.length === 0 && (
              <p className="text-center text-gray-400 text-xs py-6">No recent activity</p>
            )}
          </div>
        </ChartCard>
      </div>
    </div>
  );
}

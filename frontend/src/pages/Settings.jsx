import { useState } from "react";

export default function Settings() {
  const [activeTab, setActiveTab] = useState("general");
  const [settings, setSettings] = useState({
    theme: "dark",
    language: "en",
    auto_enrich: true,
    max_crawl_pages: 5,
    crawl_delay: 2,
    concurrent_requests: 16,
    ai_model: "gemini-2.0-flash",
    export_format: "csv",
    data_retention_days: 90,
  });

  const updateSetting = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const tabs = [
    { id: "general", label: "General" },
    { id: "crawler", label: "Crawler" },
    { id: "ai", label: "AI Settings" },
    { id: "export", label: "Export" },
    { id: "data", label: "Data" },
  ];

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Settings</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">Configure your BuyerHunter platform</p>
      </div>

      <div className="flex gap-1 border-b border-gray-200 dark:border-dark-700">
        {tabs.map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.id ? "border-brand-600 text-brand-600 dark:text-brand-400" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="glass-card p-6 max-w-2xl">
        {activeTab === "general" && (
          <div className="space-y-5">
            <h3 className="font-semibold text-gray-900 dark:text-white">General Settings</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Theme</label>
              <select className="input" value={settings.theme} onChange={(e) => updateSetting("theme", e.target.value)}>
                <option value="dark">Dark Mode</option>
                <option value="light">Light Mode</option>
                <option value="system">System Default</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Language</label>
              <select className="input" value={settings.language} onChange={(e) => updateSetting("language", e.target.value)}>
                <option value="en">English</option>
                <option value="hi">Hindi</option>
              </select>
            </div>
            <div className="flex items-center gap-3">
              <input type="checkbox" checked={settings.auto_enrich} onChange={(e) => updateSetting("auto_enrich", e.target.checked)} className="rounded border-gray-300" />
              <label className="text-sm text-gray-700 dark:text-gray-300">Auto-enrich new companies</label>
            </div>
          </div>
        )}

        {activeTab === "crawler" && (
          <div className="space-y-5">
            <h3 className="font-semibold text-gray-900 dark:text-white">Crawler Settings</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Pages Per Crawl</label>
              <input type="number" className="input" value={settings.max_crawl_pages} onChange={(e) => updateSetting("max_crawl_pages", parseInt(e.target.value))} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Download Delay (seconds)</label>
              <input type="number" className="input" value={settings.crawl_delay} onChange={(e) => updateSetting("crawl_delay", parseInt(e.target.value))} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Concurrent Requests</label>
              <input type="number" className="input" value={settings.concurrent_requests} onChange={(e) => updateSetting("concurrent_requests", parseInt(e.target.value))} />
            </div>
          </div>
        )}

        {activeTab === "ai" && (
          <div className="space-y-5">
            <h3 className="font-semibold text-gray-900 dark:text-white">AI Settings</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">AI Model</label>
              <select className="input" value={settings.ai_model} onChange={(e) => updateSetting("ai_model", e.target.value)}>
                <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
              </select>
            </div>
            <p className="text-xs text-gray-400">AI scoring uses rule-based fallback when API key is not configured.</p>
          </div>
        )}

        {activeTab === "export" && (
          <div className="space-y-5">
            <h3 className="font-semibold text-gray-900 dark:text-white">Export Settings</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Default Export Format</label>
              <select className="input" value={settings.export_format} onChange={(e) => updateSetting("export_format", e.target.value)}>
                <option value="csv">CSV</option>
                <option value="excel">Excel</option>
                <option value="json">JSON</option>
              </select>
            </div>
          </div>
        )}

        {activeTab === "data" && (
          <div className="space-y-5">
            <h3 className="font-semibold text-gray-900 dark:text-white">Data Retention</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Keep data for (days)</label>
              <input type="number" className="input" value={settings.data_retention_days} onChange={(e) => updateSetting("data_retention_days", parseInt(e.target.value))} />
              <p className="text-xs text-gray-400 mt-1">Crawl logs older than this will be automatically cleaned up.</p>
            </div>
          </div>
        )}

        <div className="mt-6 pt-4 border-t border-gray-100 dark:border-dark-700">
          <button className="btn-primary">Save Settings</button>
        </div>
      </div>
    </div>
  );
}

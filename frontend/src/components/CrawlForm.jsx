import { useState, useEffect } from "react";
import { startCrawl, getCrawlStatus } from "../api/client";

const SPIDER_GROUPS = {
  "Business Directories": ["indiamart", "justdial", "tradeindia", "yellowpages", "exportersindia"],
  "Company Websites": ["companywebsite"],
  "Trade Associations": ["tradeassociation"],
  "Government Directories": ["gst_directory"],
  "Trade Exhibitions": ["tradeexhibition"],
  "Maps & Social": ["googlemaps", "linkedin"],
};

export default function CrawlForm() {
  const [selectedSpiders, setSelectedSpiders] = useState(["indiamart"]);
  const [keywords, setKeywords] = useState("Palm Oil Wholesale India");
  const [maxPages, setMaxPages] = useState(3);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState([]);

  useEffect(() => {
    getCrawlStatus()
      .then((r) => setRunning(r.data.running || []))
      .catch(() => {});
  }, []);

  const toggleSpider = (name) => {
    setSelectedSpiders((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (selectedSpiders.length === 0) return;

    setLoading(true);
    setResult(null);
    try {
      if (selectedSpiders.length === 1) {
        const resp = await startCrawl({
          spider_name: selectedSpiders[0],
          keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
          max_pages: maxPages,
        });
        setResult({ type: "success", message: `Started ${selectedSpiders[0]}` });
      } else {
        const resp = await startCrawl({
          query: keywords.split(",").map((k) => k.trim()).filter(Boolean).join(" "),
          source: "crawl_form",
          max_pages: maxPages,
          metadata: { spiders: selectedSpiders },
        });
        setResult({ type: "success", message: resp.data?.message || `Started ${selectedSpiders.length} spiders` });
      }
    } catch (err) {
      setResult({ type: "error", message: err.response?.data?.detail || err.message });
    }
    setLoading(false);
  };

  const input = "border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500";

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm border p-6 mb-6">
      <h3 className="text-lg font-semibold mb-4">Start New Crawl</h3>

      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">Select Spiders</label>
        {Object.entries(SPIDER_GROUPS).map(([group, spiders]) => (
          <div key={group} className="mb-2">
            <p className="text-xs text-gray-500 mb-1">{group}</p>
            <div className="flex flex-wrap gap-2">
              {spiders.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => toggleSpider(name)}
                  className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                    selectedSpiders.includes(name)
                      ? "bg-primary-100 border-primary-500 text-primary-700"
                      : "bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {name}
                  {running.includes(name) && <span className="ml-1 animate-pulse">●</span>}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <input
          className={input}
          placeholder="Keywords (comma separated)"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
        />
        <input
          className={input}
          type="number"
          placeholder="Max pages"
          value={maxPages}
          min={1}
          max={20}
          onChange={(e) => setMaxPages(Number(e.target.value))}
        />
        <button
          type="submit"
          disabled={loading || selectedSpiders.length === 0}
          className="bg-primary-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "Starting..." : `Start ${selectedSpiders.length || ""} Spider${selectedSpiders.length !== 1 ? "s" : ""}`}
        </button>
      </div>

      {result && (
        <div className={`text-sm mt-2 ${result.type === "error" ? "text-red-600" : "text-green-600"}`}>
          {result.type === "error" ? `Error: ${result.message}` : result.message}
        </div>
      )}
    </form>
  );
}

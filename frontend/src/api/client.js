import axios from "axios";

// In production (Vercel), VITE_API_URL points to the Render backend.
// In local dev, Vite proxy forwards /api to localhost:8001.
const baseURL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v2`
  : "/api/v2";

const api = axios.create({ baseURL });

// ── Global Search ────────────────────────────────────────────────────────────
export const globalSearch = (params) => api.get("/search", { params });

// ── Companies ────────────────────────────────────────────────────────────────
export const getCompanies = (params) => api.get("/companies", { params });
export const getCompany = (id) => api.get(`/company/${id}`);
export const getCompanyContacts = (id) => api.get(`/company/${id}/contacts`);

// ── Products ─────────────────────────────────────────────────────────────────
export const getProducts = (params) => api.get("/companies", { params });

// ── Crawling ─────────────────────────────────────────────────────────────────
export const startCrawl = (data) => api.post("/search", data);
export const startMultiCrawl = (data) => api.post("/search", data);
export const startAllCrawls = (params) => api.post("/search", { query: "all", ...params });
export const getCrawlStatus = () => api.get("/crawl/status");

// ── Enrichment ───────────────────────────────────────────────────────────────
export const enrichCompany = (id) => api.post(`/company/${id}/refresh`);
export const enrichBatch = (params) => api.post("/company/0/refresh", params);
export const getEnrichStatus = () => api.get("/health");

// ── Classification ───────────────────────────────────────────────────────────
export const classifyLeads = (params) => api.post("/search", { query: "classify", ...params });

// ── Export ───────────────────────────────────────────────────────────────────
export const exportLeads = (format, params) =>
  api.post(`/export`, null, { params: { format, ...params }, responseType: "blob" });

// ── Stats ────────────────────────────────────────────────────────────────────
export const getStats = () => api.get("/stats");

// ── Crawl Logs ───────────────────────────────────────────────────────────────
export const getCrawlLogs = (params) => api.get("/crawl-logs", { params });

// ── Spiders ──────────────────────────────────────────────────────────────────
export const getSpiders = () => api.get("/spiders");

// ── APEDA Import ─────────────────────────────────────────────────────────────
export const importApeda = (params) => api.post("/search", { query: "import apeda", ...params });

// ── DGCIS Import ─────────────────────────────────────────────────────────────
export const importDgcis = (params) => api.post("/search", { query: "import dgcis", ...params });

// ── Trade Data ───────────────────────────────────────────────────────────────
export const getTradeData = (params) => api.get("/trade-data", { params });
export const getTradeSummary = () => api.get("/trade-summary");

// ── Lead Discovery Pipeline ──────────────────────────────────────────────────
export const startPipeline = (data) => api.post("/pipeline/start", data);
export const getPipelineProgress = (runId) => api.get(`/pipeline/${runId}/progress`);
export const getActivePipelines = () => api.get("/pipeline/active");
export const expandQuery = (query, maxQueries) => api.get("/pipeline/expand", { params: { query, max_queries: maxQueries || 500 } });

// ── Pipeline SSE stream ──────────────────────────────────────────────────────
export const streamPipeline = (runId, onMessage) => {
  const sseBase = import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}/api/v2`
    : "/api/v2";
  const eventSource = new EventSource(`${sseBase}/pipeline/${runId}/stream`);
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error("SSE parse error:", e);
    }
  };
  eventSource.onerror = () => eventSource.close();
  return eventSource;
};

// ── Discovery Engine ─────────────────────────────────────────────────────────
export const getDiscoverySources = () => api.get("/discovery/sources");
export const getDiscoveryPlan = (query, maxQueries) => api.post("/search", { query, max_queries: maxQueries || 500 });
export const getDiscoveryCompanies = (runId, params) => api.get(`/search/${runId}`, { params });
export const getDiscoveryStats = () => api.get("/discovery/stats");

// ── Analytics ────────────────────────────────────────────────────────────────
export const getAnalyticsStates = () => api.get("/stats");
export const getAnalyticsIndustries = () => api.get("/stats");
export const getAnalyticsSources = () => api.get("/stats");
export const getAnalyticsTopBuyers = (params) => api.get("/companies", { params: { ...params, is_manufacturer: false, sort_by: "buyer_score" } });
export const getAnalyticsTopManufacturers = (params) => api.get("/companies", { params: { ...params, is_manufacturer: true, sort_by: "buyer_score" } });
export const getAnalyticsTopDistributors = (params) => api.get("/companies", { params: { ...params, is_distributor: true, sort_by: "buyer_score" } });
export const getAnalyticsTopImporters = (params) => api.get("/companies", { params: { ...params, is_importer: true, sort_by: "buyer_score" } });
export const getAnalyticsTopExporters = (params) => api.get("/companies", { params: { ...params, is_exporter: true, sort_by: "buyer_score" } });

export default api;

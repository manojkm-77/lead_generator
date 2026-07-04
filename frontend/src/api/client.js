import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// Global Search
export const globalSearch = (params) => api.get("/search", { params });

// Companies
export const getCompanies = (params) => api.get("/companies", { params });
export const getCompany = (id) => api.get(`/company/${id}`);
export const getCompanyContacts = (id) => api.get(`/company/${id}/contacts`);

// Products
export const getProducts = (params) => api.get("/products", { params });

// Crawling
export const startCrawl = (data) => api.post("/crawl", data);
export const startMultiCrawl = (data) => api.post("/crawl/multi", data);
export const startAllCrawls = (params) => api.post("/crawl/all", null, { params });
export const getCrawlStatus = () => api.get("/crawl/status");

// Enrichment
export const enrichCompany = (id) => api.post(`/enrich/${id}`);
export const enrichBatch = (params) => api.post("/enrich/batch", null, { params });
export const getEnrichStatus = () => api.get("/enrich/status");

// Classification
export const classifyLeads = (params) => api.post("/classify", null, { params });

// Export
export const exportLeads = (format, params) =>
  api.post(`/export`, null, { params: { format, ...params }, responseType: "blob" });

// Stats
export const getStats = () => api.get("/stats");

// Crawl Logs
export const getCrawlLogs = (params) => api.get("/crawl-logs", { params });

// Spiders
export const getSpiders = () => api.get("/spiders");

// APEDA Import
export const importApeda = (params) => api.post("/import/apeda", null, { params });

// DGCIS Import
export const importDgcis = (params) => api.post("/import/dgcis", null, { params });

// Trade Data
export const getTradeData = (params) => api.get("/trade-data", { params });
export const getTradeSummary = () => api.get("/trade-summary");

// ── Lead Discovery Pipeline ──────────────────────────────────────────────────
export const startPipeline = (data) => api.post("/pipeline/start", data);
export const getPipelineProgress = (runId) => api.get(`/pipeline/${runId}/progress`);
export const getActivePipelines = () => api.get("/pipeline/active");
export const expandQuery = (query) => api.get("/pipeline/expand", { params: { query } });

// Pipeline SSE stream
export const streamPipeline = (runId, onMessage) => {
  const eventSource = new EventSource(`/api/pipeline/${runId}/stream`);
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

// ── Analytics ────────────────────────────────────────────────────────────────
export const getAnalyticsStates = () => api.get("/analytics/states");
export const getAnalyticsIndustries = () => api.get("/analytics/industries");
export const getAnalyticsSources = () => api.get("/analytics/sources");
export const getAnalyticsTopBuyers = (params) => api.get("/analytics/top-buyers", { params });
export const getAnalyticsTopManufacturers = (params) => api.get("/analytics/top-manufacturers", { params });
export const getAnalyticsTopDistributors = (params) => api.get("/analytics/top-distributors", { params });
export const getAnalyticsTopImporters = (params) => api.get("/analytics/top-importers", { params });
export const getAnalyticsTopExporters = (params) => api.get("/analytics/top-exporters", { params });

export default api;

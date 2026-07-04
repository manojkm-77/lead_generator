import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// Intelligence
export const getBuyerIntelligence = (params) => api.get("/buyer-intelligence", { params });
export const getProcurementContacts = (params) => api.get("/procurement-contacts", { params });
export const getTopBuyers = (params) => api.get("/top-buyers", { params });
export const getIntelligence = (id) => api.get(`/intelligence/${id}`);
export const getIntelligenceStats = () => api.get("/intelligence/stats");
export const analyzeCompany = (id) => api.post(`/analyze-company/${id}`);
export const analyzeAll = (params) => api.post("/analyze-all", null, { params });

export default api;

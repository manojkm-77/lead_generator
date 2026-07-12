import axios from "axios";

const api = axios.create({ baseURL: "/api/v2" });

// Intelligence
export const getBuyerIntelligence = (params) => api.get("/companies", { params });
export const getProcurementContacts = (params) => api.get("/companies", { params });
export const getTopBuyers = (params) => api.get("/companies", { params: { ...params, is_manufacturer: false, sort_by: "buyer_score" } });
export const getIntelligence = (id) => api.get(`/company/${id}`);
export const getIntelligenceStats = () => api.get("/stats");
export const analyzeCompany = (id) => api.post(`/company/${id}/refresh`);
export const analyzeAll = (params) => api.post("/search", { query: "classify", ...params });

export default api;

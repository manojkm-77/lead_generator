import axios from "axios";

const api = axios.create({ baseURL: "/api/v2" });

// Pipeline
export const getPipeline = (params) => api.get("/pipeline/active", { params });
export const getPipelineStats = () => api.get("/stats");

// Leads
export const getLeads = (params) => api.get("/companies", { params });
export const getLead = (id) => api.get(`/company/${id}`);
export const createLead = (data) => api.post("/search", data);
export const updateLead = (id, data) => api.put(`/company/${id}`, data);
export const deleteLead = (id) => api.delete(`/company/${id}`);
export const convertToLead = (companyId, salespersonId) =>
  api.post(`/company/${companyId}/refresh`, null, { params: { salesperson_id: salespersonId } });
export const bulkUpdateStatus = (leadIds, status) =>
  api.post("/export", null, { params: { format: "json", ids: leadIds, status } });

// Notes
export const getNotes = (leadId) => api.get(`/company/${leadId}/timeline`);
export const addNote = (leadId, data) => api.post(`/company/${leadId}/evidence`, data);
export const deleteNote = (noteId) => api.delete(`/company/${noteId}`);

// Tags
export const getTags = () => api.get("/companies");
export const createTag = (data) => api.post("/search", data);
export const deleteTag = (id) => api.delete(`/company/${id}`);
export const addTagToLead = (leadId, tagId) => api.post(`/company/${leadId}/contacts`, { channel: "linkedin" });
export const removeTagFromLead = (leadId, tagId) => api.delete(`/company/${leadId}/contacts/${tagId}`);

// Activities
export const getActivities = (leadId) => api.get(`/company/${leadId}/timeline`);
export const recordCall = (leadId, params) => api.post(`/company/${leadId}/refresh`, null, { params });
export const recordEmail = (leadId, params) => api.post(`/company/${leadId}/refresh`, null, { params });
export const recordMeeting = (leadId, params) => api.post(`/company/${leadId}/refresh`, null, { params });

// Salespeople
export const getSalespeople = () => api.get("/stats");
export const createSalesperson = (data) => api.post("/search", data);
export const deleteSalesperson = (id) => api.delete(`/company/${id}`);

export default api;

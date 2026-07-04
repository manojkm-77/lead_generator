import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// Pipeline
export const getPipeline = (params) => api.get("/pipeline", { params });
export const getPipelineStats = () => api.get("/pipeline/stats");

// Leads
export const getLeads = (params) => api.get("/leads", { params });
export const getLead = (id) => api.get(`/leads/${id}`);
export const createLead = (data) => api.post("/leads", data);
export const updateLead = (id, data) => api.put(`/leads/${id}`, data);
export const deleteLead = (id) => api.delete(`/leads/${id}`);
export const convertToLead = (companyId, salespersonId) =>
  api.post(`/leads/${companyId}/convert`, null, { params: { salesperson_id: salespersonId } });
export const bulkUpdateStatus = (leadIds, status) =>
  api.post("/leads/bulk-status", leadIds, { params: { status } });

// Notes
export const getNotes = (leadId) => api.get(`/leads/${leadId}/notes`);
export const addNote = (leadId, data) => api.post(`/leads/${leadId}/notes`, data);
export const deleteNote = (noteId) => api.delete(`/notes/${noteId}`);

// Tags
export const getTags = () => api.get("/tags");
export const createTag = (data) => api.post("/tags", data);
export const deleteTag = (id) => api.delete(`/tags/${id}`);
export const addTagToLead = (leadId, tagId) => api.post(`/leads/${leadId}/tags/${tagId}`);
export const removeTagFromLead = (leadId, tagId) => api.delete(`/leads/${leadId}/tags/${tagId}`);

// Activities
export const getActivities = (leadId) => api.get(`/leads/${leadId}/activities`);
export const recordCall = (leadId, params) => api.post(`/leads/${leadId}/call`, null, { params });
export const recordEmail = (leadId, params) => api.post(`/leads/${leadId}/email`, null, { params });
export const recordMeeting = (leadId, params) => api.post(`/leads/${leadId}/meeting`, null, { params });

// Salespeople
export const getSalespeople = () => api.get("/salespeople");
export const createSalesperson = (data) => api.post("/salespeople", data);
export const deleteSalesperson = (id) => api.delete(`/salespeople/${id}`);

export default api;

import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  getLead, updateLead, deleteLead,
  getNotes, addNote,
  getTags, addTagToLead, removeTagFromLead,
  getActivities, recordCall, recordEmail, recordMeeting,
  getSalespeople,
} from "../api/crm";

const STATUS_OPTIONS = [
  { value: "cold", label: "Cold", color: "bg-blue-100 text-blue-700" },
  { value: "warm", label: "Warm", color: "bg-yellow-100 text-yellow-700" },
  { value: "hot", label: "Hot", color: "bg-orange-100 text-orange-700" },
  { value: "interested", label: "Interested", color: "bg-purple-100 text-purple-700" },
  { value: "negotiation", label: "Negotiation", color: "bg-indigo-100 text-indigo-700" },
  { value: "won", label: "Won", color: "bg-green-100 text-green-700" },
  { value: "lost", label: "Lost", color: "bg-red-100 text-red-700" },
];

const PRIORITY_OPTIONS = ["low", "medium", "high", "urgent"];

const ACTIVITY_ICONS = {
  call: "📞", email: "📧", meeting: "🤝", note: "📝",
  status_change: "🔄", assignment: "👤", created: "✨", followup: "📅",
};

function StatusBadge({ status }) {
  const s = STATUS_OPTIONS.find((o) => o.value === status) || STATUS_OPTIONS[0];
  return <span className={`px-2 py-1 rounded-full text-xs font-medium ${s.color}`}>{s.label}</span>;
}

export default function LeadDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [lead, setLead] = useState(null);
  const [notes, setNotes] = useState([]);
  const [activities, setActivities] = useState([]);
  const [allTags, setAllTags] = useState([]);
  const [salespeople, setSalespeople] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newNote, setNewNote] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState({});
  const [showRecordMenu, setShowRecordMenu] = useState(false);

  const load = async () => {
    try {
      const [l, n, a, t, sp] = await Promise.all([
        getLead(id), getNotes(id), getActivities(id), getTags(), getSalespeople(),
      ]);
      setLead(l.data); setNotes(n.data); setActivities(a.data);
      setAllTags(t.data); setSalespeople(sp.data);
      setEditData({
        status: l.data.status, priority: l.data.priority,
        deal_value: l.data.deal_value || "", salesperson_id: l.data.salesperson_id || "",
        next_followup: l.data.next_followup ? l.data.next_followup.slice(0, 16) : "",
        followup_notes: l.data.followup_notes || "", lost_reason: l.data.lost_reason || "",
      });
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [id]);

  const handleSave = async () => {
    const data = { ...editData };
    if (data.deal_value) data.deal_value = parseInt(data.deal_value) || null;
    else data.deal_value = null;
    if (data.salesperson_id) data.salesperson_id = parseInt(data.salesperson_id) || null;
    else data.salesperson_id = null;
    if (data.next_followup) data.next_followup = new Date(data.next_followup).toISOString();
    else data.next_followup = null;
    await updateLead(id, data);
    setEditMode(false);
    load();
  };

  const handleAddNote = async () => {
    if (!newNote.trim()) return;
    await addNote(id, { content: newNote });
    setNewNote("");
    const r = await getNotes(id);
    setNotes(r.data);
  };

  const handleRecord = async (type) => {
    if (type === "call") await recordCall(id);
    else if (type === "email") await recordEmail(id);
    else if (type === "meeting") await recordMeeting(id);
    setShowRecordMenu(false);
    load();
  };

  const handleTagToggle = async (tagId) => {
    const hasTag = lead.tags?.includes(allTags.find((t) => t.id === tagId)?.name);
    if (hasTag) await removeTagFromLead(id, tagId);
    else await addTagToLead(id, tagId);
    load();
  };

  const handleDelete = async () => {
    if (confirm("Delete this lead?")) {
      await deleteLead(id);
      navigate("/crm/pipeline");
    }
  };

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;
  if (!lead) return <div className="text-center py-12 text-gray-500">Lead not found</div>;

  const input = "border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 w-full";

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <Link to="/crm/pipeline" className="text-primary-600 hover:underline text-sm">&larr; Pipeline</Link>
          <h1 className="text-2xl font-bold mt-1">{lead.company_name}</h1>
        </div>
        <div className="flex gap-2">
          <div className="relative">
            <button onClick={() => setShowRecordMenu(!showRecordMenu)} className="px-3 py-2 border rounded-lg text-sm hover:bg-gray-50">
              Record Activity
            </button>
            {showRecordMenu && (
              <div className="absolute right-0 mt-1 bg-white border rounded-lg shadow-lg z-10 w-40">
                {["call", "email", "meeting"].map((t) => (
                  <button key={t} onClick={() => handleRecord(t)} className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-50 capitalize">{t}</button>
                ))}
              </div>
            )}
          </div>
          <button onClick={() => setEditMode(!editMode)} className="px-3 py-2 border rounded-lg text-sm hover:bg-gray-50">
            {editMode ? "Cancel" : "Edit"}
          </button>
          <button onClick={handleDelete} className="px-3 py-2 border border-red-300 text-red-600 rounded-lg text-sm hover:bg-red-50">
            Delete
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Status & Pipeline */}
          <div className="bg-white rounded-lg border p-6">
            <h3 className="font-semibold mb-4">Pipeline</h3>
            {editMode ? (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-gray-500">Status</label>
                  <select className={input} value={editData.status} onChange={(e) => setEditData({...editData, status: e.target.value})}>
                    {STATUS_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-sm text-gray-500">Priority</label>
                  <select className={input} value={editData.priority} onChange={(e) => setEditData({...editData, priority: e.target.value})}>
                    {PRIORITY_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-sm text-gray-500">Deal Value (₹)</label>
                  <input type="number" className={input} value={editData.deal_value} onChange={(e) => setEditData({...editData, deal_value: e.target.value})} />
                </div>
                <div>
                  <label className="text-sm text-gray-500">Salesperson</label>
                  <select className={input} value={editData.salesperson_id} onChange={(e) => setEditData({...editData, salesperson_id: e.target.value})}>
                    <option value="">Unassigned</option>
                    {salespeople.map((sp) => <option key={sp.id} value={sp.id}>{sp.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-sm text-gray-500">Next Follow-up</label>
                  <input type="datetime-local" className={input} value={editData.next_followup} onChange={(e) => setEditData({...editData, next_followup: e.target.value})} />
                </div>
                <div>
                  <label className="text-sm text-gray-500">Follow-up Notes</label>
                  <input className={input} value={editData.followup_notes} onChange={(e) => setEditData({...editData, followup_notes: e.target.value})} />
                </div>
                {editData.status === "lost" && (
                  <div className="col-span-2">
                    <label className="text-sm text-gray-500">Lost Reason</label>
                    <input className={input} value={editData.lost_reason} onChange={(e) => setEditData({...editData, lost_reason: e.target.value})} />
                  </div>
                )}
                <div className="col-span-2">
                  <button onClick={handleSave} className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm">Save</button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div><p className="text-gray-500">Status</p><StatusBadge status={lead.status} /></div>
                <div><p className="text-gray-500">Priority</p><p className="capitalize">{lead.priority}</p></div>
                <div><p className="text-gray-500">Deal Value</p><p>{lead.deal_value ? `₹${lead.deal_value.toLocaleString()}` : "-"}</p></div>
                <div><p className="text-gray-500">Salesperson</p><p>{lead.salesperson_name || "Unassigned"}</p></div>
                <div><p className="text-gray-500">Next Follow-up</p><p>{lead.next_followup ? new Date(lead.next_followup).toLocaleString() : "-"}</p></div>
                <div><p className="text-gray-500">Last Contact</p><p>{lead.last_contacted ? new Date(lead.last_contacted).toLocaleDateString() : "-"}</p></div>
                {lead.lost_reason && <div className="col-span-2"><p className="text-gray-500">Lost Reason</p><p>{lead.lost_reason}</p></div>}
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="bg-white rounded-lg border p-6">
            <h3 className="font-semibold mb-4">Notes</h3>
            <div className="flex gap-2 mb-4">
              <input className={input} placeholder="Add a note..." value={newNote} onChange={(e) => setNewNote(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAddNote()} />
              <button onClick={handleAddNote} className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm">Add</button>
            </div>
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {notes.map((n) => (
                <div key={n.id} className="bg-gray-50 rounded p-3">
                  <p className="text-sm">{n.content}</p>
                  <p className="text-xs text-gray-400 mt-1">{n.created_by || "System"} · {new Date(n.created_at).toLocaleString()}</p>
                </div>
              ))}
              {notes.length === 0 && <p className="text-gray-400 text-sm">No notes yet</p>}
            </div>
          </div>

          {/* Activity Timeline */}
          <div className="bg-white rounded-lg border p-6">
            <h3 className="font-semibold mb-4">Activity Timeline</h3>
            <div className="space-y-3">
              {activities.map((a) => (
                <div key={a.id} className="flex gap-3">
                  <span className="text-lg">{ACTIVITY_ICONS[a.activity_type] || "📌"}</span>
                  <div>
                    <p className="text-sm font-medium">{a.title || a.activity_type}</p>
                    {a.description && <p className="text-xs text-gray-500">{a.description}</p>}
                    <p className="text-xs text-gray-400">{new Date(a.created_at).toLocaleString()}</p>
                  </div>
                </div>
              ))}
              {activities.length === 0 && <p className="text-gray-400 text-sm">No activities yet</p>}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Company Info */}
          <div className="bg-white rounded-lg border p-6">
            <h3 className="font-semibold mb-3">Company Info</h3>
            <div className="text-sm space-y-2">
              <p><span className="text-gray-500">Industry:</span> {lead.company_industry || "-"}</p>
              <p><span className="text-gray-500">City:</span> {lead.company_city || "-"}</p>
              <p><span className="text-gray-500">Score:</span> {lead.company_lead_score || 0}</p>
              {lead.company_website && (
                <p><a href={lead.company_website} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">Website →</a></p>
              )}
            </div>
            <Link to={`/company/${lead.company_id}`} className="block mt-3 text-sm text-primary-600 hover:underline">
              View Full Profile →
            </Link>
          </div>

          {/* Tags */}
          <div className="bg-white rounded-lg border p-6">
            <h3 className="font-semibold mb-3">Tags</h3>
            <div className="flex flex-wrap gap-2 mb-3">
              {lead.tags?.map((tag) => (
                <span key={tag} className="px-2 py-1 bg-primary-100 text-primary-700 rounded text-xs">{tag}</span>
              ))}
              {(!lead.tags || lead.tags.length === 0) && <p className="text-gray-400 text-sm">No tags</p>}
            </div>
            <div className="flex flex-wrap gap-1">
              {allTags.map((t) => {
                const has = lead.tags?.includes(t.name);
                return (
                  <button key={t.id} onClick={() => handleTagToggle(t.id)}
                    className={`px-2 py-1 text-xs rounded border ${has ? "bg-primary-500 text-white" : "bg-gray-50 hover:bg-gray-100"}`}>
                    {t.name}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

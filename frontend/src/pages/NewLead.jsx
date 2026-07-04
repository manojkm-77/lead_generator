import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { createLead, getSalespeople } from "../api/crm";
import { getCompanies } from "../api/client";

export default function NewLead() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState([]);
  const [salespeople, setSalespeople] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState({
    company_id: null,
    salesperson_id: null,
    status: "cold",
    deal_value: "",
    priority: "medium",
    next_followup: "",
    followup_notes: "",
  });

  useEffect(() => {
    Promise.all([getCompanies({ page_size: 100 }), getSalespeople()])
      .then(([c, sp]) => { setCompanies(c.data.companies); setSalespeople(sp.data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = companies.filter((c) =>
    c.company_name.toLowerCase().includes(search.toLowerCase())
  );

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.company_id) return;
    const data = { ...form };
    if (data.deal_value) data.deal_value = parseInt(data.deal_value) || null;
    else data.deal_value = null;
    if (data.salesperson_id) data.salesperson_id = parseInt(data.salesperson_id) || null;
    else data.salesperson_id = null;
    if (data.next_followup) data.next_followup = new Date(data.next_followup).toISOString();
    else data.next_followup = null;
    try {
      const r = await createLead(data);
      navigate(`/crm/lead/${r.data.id}`);
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to create lead");
    }
  };

  const input = "border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 w-full";

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;

  return (
    <div>
      <Link to="/crm/pipeline" className="text-primary-600 hover:underline text-sm">&larr; Pipeline</Link>
      <h1 className="text-2xl font-bold mt-2 mb-6">New Lead</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg border p-6 max-w-2xl space-y-4">
        {/* Company Search */}
        <div>
          <label className="text-sm text-gray-500 mb-1 block">Company *</label>
          <input className={input} placeholder="Search company..." value={search} onChange={(e) => setSearch(e.target.value)} />
          {search && !form.company_id && (
            <div className="mt-1 max-h-48 overflow-y-auto border rounded-lg">
              {filtered.slice(0, 20).map((c) => (
                <button key={c.id} type="button" onClick={() => { setForm({...form, company_id: c.id}); setSearch(c.company_name); }}
                  className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-50">
                  {c.company_name} <span className="text-gray-400">({c.city || "N/A"})</span>
                </button>
              ))}
            </div>
          )}
          {form.company_id && <p className="text-sm text-green-600 mt-1">Selected ✓</p>}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-gray-500 mb-1 block">Status</label>
            <select className={input} value={form.status} onChange={(e) => setForm({...form, status: e.target.value})}>
              {["cold", "warm", "hot", "interested", "negotiation"].map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm text-gray-500 mb-1 block">Priority</label>
            <select className={input} value={form.priority} onChange={(e) => setForm({...form, priority: e.target.value})}>
              {["low", "medium", "high", "urgent"].map((p) => (
                <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-gray-500 mb-1 block">Deal Value (₹)</label>
            <input type="number" className={input} value={form.deal_value} onChange={(e) => setForm({...form, deal_value: e.target.value})} />
          </div>
          <div>
            <label className="text-sm text-gray-500 mb-1 block">Salesperson</label>
            <select className={input} value={form.salesperson_id || ""} onChange={(e) => setForm({...form, salesperson_id: e.target.value})}>
              <option value="">Unassigned</option>
              {salespeople.map((sp) => <option key={sp.id} value={sp.id}>{sp.name}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-gray-500 mb-1 block">Next Follow-up</label>
            <input type="datetime-local" className={input} value={form.next_followup} onChange={(e) => setForm({...form, next_followup: e.target.value})} />
          </div>
          <div>
            <label className="text-sm text-gray-500 mb-1 block">Follow-up Notes</label>
            <input className={input} value={form.followup_notes} onChange={(e) => setForm({...form, followup_notes: e.target.value})} />
          </div>
        </div>

        <button type="submit" disabled={!form.company_id} className="px-6 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700 disabled:opacity-50">
          Create Lead
        </button>
      </form>
    </div>
  );
}

import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { getCompany, getCompanyContacts, enrichCompany } from "../api/client";

function ScoreGauge({ score, label }) {
  const r = 50, s = 7, nr = r - s, c = nr * 2 * Math.PI;
  const offset = c - (score / 100) * c;
  const color = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : score >= 20 ? "#f97316" : "#6b7280";
  return (
    <div className="relative inline-flex items-center justify-center">
      <svg height={r * 2} width={r * 2}>
        <circle stroke="#e5e7eb" fill="transparent" strokeWidth={s} r={nr} cx={r} cy={r} className="dark:stroke-dark-700" />
        <circle stroke={color} fill="transparent" strokeWidth={s} strokeLinecap="round"
          strokeDasharray={c + " " + c} style={{ strokeDashoffset: offset, transition: "stroke-dashoffset 0.5s ease" }}
          r={nr} cx={r} cy={r} transform={`rotate(-90 ${r} ${r})`} />
      </svg>
      <div className="absolute text-center">
        <p className="text-2xl font-bold text-gray-900 dark:text-white">{score}</p>
        {label && <p className="text-[10px] text-gray-500">{label}</p>}
      </div>
    </div>
  );
}

function InfoItem({ label, value, icon, link }) {
  if (!value) return null;
  const content = (
    <div className="flex items-start gap-3 py-2.5">
      <svg className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icon} />
      </svg>
      <div className="min-w-0">
        <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
        <p className="text-sm text-gray-900 dark:text-white break-words">{value}</p>
      </div>
    </div>
  );
  if (link) return <a href={link} target="_blank" rel="noreferrer" className="block hover:bg-gray-50 dark:hover:bg-dark-700 rounded-lg px-2 -mx-2">{content}</a>;
  return content;
}

function TagBadge({ text, color = "gray" }) {
  if (!text) return null;
  const colors = {
    green: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    blue: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    yellow: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    red: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    purple: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
    gray: "bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-gray-400",
  };
  return <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${colors[color]}`}>{text}</span>;
}

const TABS = ["Overview", "Products", "Contacts", "Trade", "AI Insights"];

export default function CompanyView() {
  const { id } = useParams();
  const [company, setCompany] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);
  const [activeTab, setActiveTab] = useState("Overview");

  useEffect(() => {
    setLoading(true);
    Promise.all([getCompany(id), getCompanyContacts(id).catch(() => ({ data: { contacts: [] } }))])
      .then(([c, ct]) => { setCompany(c.data); setContacts(ct.data.contacts || []); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  const handleEnrich = async () => {
    setEnriching(true);
    try {
      await enrichCompany(id);
      setTimeout(async () => {
        const r = await getCompany(id);
        setCompany(r.data);
        setEnriching(false);
      }, 3000);
    } catch { setEnriching(false); }
  };

  if (loading) return (
    <div className="space-y-4">
      <div className="animate-pulse h-8 bg-gray-200 dark:bg-dark-700 rounded w-1/3"></div>
      <div className="animate-pulse h-4 bg-gray-200 dark:bg-dark-700 rounded w-1/2"></div>
      <div className="grid grid-cols-3 gap-4 mt-6">
        {Array(6).fill(0).map((_, i) => <div key={i} className="animate-pulse h-24 bg-gray-200 dark:bg-dark-700 rounded-xl"></div>)}
      </div>
    </div>
  );

  if (!company) return (
    <div className="text-center py-12">
      <p className="text-gray-500">Company not found</p>
      <Link to="/companies" className="text-brand-600 hover:underline mt-4 inline-block">Back to Companies</Link>
    </div>
  );

  const parseJson = (str) => { if (!str) return []; try { return JSON.parse(str); } catch { return [str]; } };
  const products = parseJson(company.products);
  const brands = parseJson(company.brands);
  const exportMarkets = parseJson(company.export_markets);
  const importCountries = parseJson(company.import_countries);

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <Link to="/companies" className="text-xs text-gray-500 hover:text-brand-600 inline-flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Back to Companies
          </Link>
          <div className="flex items-center gap-3 mt-2">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white text-xl font-bold">
              {company.company_name?.charAt(0)}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{company.company_name}</h1>
              <div className="flex items-center gap-2 mt-0.5">
                {company.industry && <TagBadge text={company.industry} color="blue" />}
                {company.is_verified && <TagBadge text="Verified" color="green" />}
                {company.source && <TagBadge text={company.source} color="purple" />}
                {company.is_importer && <TagBadge text="Importer" color="yellow" />}
                {company.is_exporter && <TagBadge text="Exporter" color="green" />}
              </div>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {company.website && (
            <a href={company.website} target="_blank" rel="noreferrer" className="btn-secondary text-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
              Website
            </a>
          )}
          <button onClick={handleEnrich} disabled={enriching} className="btn-primary text-sm">
            {enriching ? "Analyzing..." : "Enrich with AI"}
          </button>
        </div>
      </div>

      {/* Score Row */}
      <div className="glass-card p-4 mb-4">
        <div className="flex items-center gap-6">
          <ScoreGauge score={company.buyer_score || company.lead_score || 0} label="Buyer" />
          <ScoreGauge score={company.confidence || company.ai_confidence || 0} label="Confidence" />
          <ScoreGauge score={company.opportunity_score || 0} label="Opportunity" />
          <div className="flex-1 grid grid-cols-4 gap-4 ml-4">
            <div><p className="text-xs text-gray-500">Size</p><p className="text-sm font-medium text-gray-900 dark:text-white">{company.estimated_size || "Unknown"}</p></div>
            <div><p className="text-xs text-gray-500">Usage</p><p className="text-sm font-medium text-gray-900 dark:text-white">{company.potential_oil_usage || "Unknown"}</p></div>
            <div><p className="text-xs text-gray-500">Frequency</p><p className="text-sm font-medium text-gray-900 dark:text-white">{company.ai_frequency || "Unknown"}</p></div>
            <div><p className="text-xs text-gray-500">Status</p><p className="text-sm font-medium text-gray-900 dark:text-white">{company.lead_status || "New"}</p></div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-dark-700 mb-4">
        {TABS.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${activeTab === tab ? "border-brand-600 text-brand-600 dark:text-brand-400" : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"}`}>
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          {activeTab === "Overview" && (
            <>
              {/* Business Details */}
              <div className="glass-card p-5">
                <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Business Details</h3>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                  <InfoItem label="GST Number" value={company.gst_number} icon="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z" />
                  <InfoItem label="CIN Number" value={company.cin_number} icon="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  <InfoItem label="IEC Code" value={company.iec_code} icon="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z" />
                  <InfoItem label="Business Type" value={company.business_type || company.industry} icon="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  <InfoItem label="Employees" value={company.employees?.toLocaleString()} icon="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  <InfoItem label="Turnover" value={company.turnover || company.revenue} icon="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  <InfoItem label="Founded" value={company.founded_year} icon="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  <InfoItem label="Google Rating" value={company.google_rating ? `${company.google_rating}/5` : null} icon="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                </div>
              </div>

              {/* Addresses */}
              <div className="glass-card p-5">
                <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Addresses</h3>
                <div className="space-y-1">
                  <InfoItem label="Primary Address" value={company.address} icon="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <InfoItem label="Factory" value={company.factory_address} icon="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" />
                  <InfoItem label="Office" value={company.office_address} icon="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  <InfoItem label="Warehouse" value={company.warehouse_address} icon="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  <InfoItem label="City" value={company.city} icon="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <InfoItem label="District" value={company.district} icon="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <InfoItem label="State" value={company.state} icon="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <InfoItem label="Country" value={company.country} icon="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
                </div>
                {company.latitude && company.longitude && (
                  <a href={`https://www.google.com/maps?q=${company.latitude},${company.longitude}`} target="_blank" rel="noreferrer"
                    className="mt-3 inline-flex items-center gap-1.5 text-xs text-brand-600 hover:text-brand-700">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /></svg>
                    View on Google Maps
                  </a>
                )}
              </div>

              {/* Certifications */}
              {(company.fssai_number || company.apeda_registration || company.iso_certification || company.haccp_certification || company.brc_certification) && (
                <div className="glass-card p-5">
                  <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Certifications</h3>
                  <div className="flex flex-wrap gap-2">
                    {company.fssai_number && <TagBadge text={`FSSAI: ${company.fssai_number}`} color="green" />}
                    {company.apeda_registration && <TagBadge text={`APEDA: ${company.apeda_registration}`} color="blue" />}
                    {company.iso_certification && <TagBadge text={`ISO: ${company.iso_certification}`} color="purple" />}
                    {company.haccp_certification && <TagBadge text={`HACCP: ${company.haccp_certification}`} color="yellow" />}
                    {company.brc_certification && <TagBadge text={`BRC: ${company.brc_certification}`} color="red" />}
                  </div>
                </div>
              )}

              {/* About */}
              {(company.about_us || company.company_description) && (
                <div className="glass-card p-5">
                  <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">About</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{company.about_us || company.company_description}</p>
                </div>
              )}
            </>
          )}

          {activeTab === "Products" && (
            <div className="glass-card p-5">
              <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Products & Brands</h3>
              {products.length > 0 ? (
                <div className="space-y-3">
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Products ({products.length})</p>
                    <div className="flex flex-wrap gap-2">
                      {products.map((p, i) => <span key={i} className="px-3 py-1.5 bg-gray-100 dark:bg-dark-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm">{p}</span>)}
                    </div>
                  </div>
                  {brands.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-500 mb-2">Brands ({brands.length})</p>
                      <div className="flex flex-wrap gap-2">
                        {brands.map((b, i) => <span key={i} className="px-3 py-1.5 bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400 rounded-lg text-sm">{b}</span>)}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-400">No products listed</p>
              )}
            </div>
          )}

          {activeTab === "Contacts" && (
            <div className="glass-card p-5">
              <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Decision Makers ({contacts.length})</h3>
              {contacts.length > 0 ? (
                <div className="space-y-2">
                  {contacts.map((c) => (
                    <div key={c.id} className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 dark:border-dark-700 hover:bg-gray-50 dark:hover:bg-dark-800">
                      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-xs font-bold">
                        {c.person_name?.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">{c.person_name}</p>
                        <p className="text-xs text-gray-500">{c.designation || "Unknown"} {c.department ? `| ${c.department}` : ""}</p>
                      </div>
                      <div className="text-right">
                        {c.email && <p className="text-xs text-gray-500">{c.email}</p>}
                        {c.phone && <p className="text-xs text-gray-500">{c.phone}</p>}
                      </div>
                      <div className="w-12 bg-gray-200 dark:bg-dark-700 rounded-full h-1.5">
                        <div className={`h-1.5 rounded-full ${c.confidence_score >= 70 ? "bg-green-500" : c.confidence_score >= 40 ? "bg-yellow-500" : "bg-gray-400"}`} style={{ width: `${c.confidence_score}%` }}></div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400">No contacts discovered yet</p>
              )}
            </div>
          )}

          {activeTab === "Trade" && (
            <>
              <div className="glass-card p-5">
                <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Trade Information</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Export Markets</p>
                    {exportMarkets.length > 0 ? (
                      <div className="flex flex-wrap gap-1">{exportMarkets.map((m, i) => <TagBadge key={i} text={m} color="green" />)}</div>
                    ) : <p className="text-xs text-gray-400">Not available</p>}
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Import Countries</p>
                    {importCountries.length > 0 ? (
                      <div className="flex flex-wrap gap-1">{importCountries.map((c, i) => <TagBadge key={i} text={c} color="blue" />)}</div>
                    ) : <p className="text-xs text-gray-400">Not available</p>}
                  </div>
                </div>
              </div>
              <div className="glass-card p-5">
                <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Business Classification</h3>
                <div className="flex flex-wrap gap-2">
                  {company.is_importer && <TagBadge text="Importer" color="yellow" />}
                  {company.is_exporter && <TagBadge text="Exporter" color="green" />}
                  {company.is_manufacturer && <TagBadge text="Manufacturer" color="blue" />}
                  {company.is_distributor && <TagBadge text="Distributor" color="purple" />}
                  {company.is_wholesaler && <TagBadge text="Wholesaler" color="red" />}
                  {company.is_retailer && <TagBadge text="Retailer" color="gray" />}
                  {!company.is_importer && !company.is_exporter && !company.is_manufacturer && !company.is_distributor && !company.is_wholesaler && !company.is_retailer && (
                    <p className="text-xs text-gray-400">No classifications available</p>
                  )}
                </div>
              </div>
            </>
          )}

          {activeTab === "AI Insights" && (
            <>
              {company.ai_reason && (
                <div className="glass-card p-5">
                  <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">AI Analysis</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{company.ai_reason}</p>
                  <div className="grid grid-cols-3 gap-4 mt-4">
                    <div><p className="text-xs text-gray-500">Confidence</p><p className="font-medium">{company.ai_confidence || 0}%</p></div>
                    <div><p className="text-xs text-gray-500">Consumption</p><p className="font-medium">{company.ai_consumption || "Unknown"}</p></div>
                    <div><p className="text-xs text-gray-500">Frequency</p><p className="font-medium">{company.ai_frequency || "Unknown"}</p></div>
                  </div>
                </div>
              )}
              <div className="glass-card p-5">
                <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Scores</h3>
                <div className="grid grid-cols-2 gap-4">
                  {[
                    { label: "Buyer Score", value: company.buyer_score || company.lead_score || 0, color: "bg-brand-500" },
                    { label: "Confidence", value: company.confidence || company.ai_confidence || 0, color: "bg-green-500" },
                    { label: "Opportunity", value: company.opportunity_score || 0, color: "bg-blue-500" },
                    { label: "Risk", value: company.risk_score || 0, color: "bg-red-500" },
                  ].map((s) => (
                    <div key={s.label}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-500">{s.label}</span>
                        <span className="text-xs font-medium">{s.value}/100</span>
                      </div>
                      <div className="w-full bg-gray-200 dark:bg-dark-700 rounded-full h-2">
                        <div className={`${s.color} h-2 rounded-full`} style={{ width: `${s.value}%` }}></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <div className="glass-card p-5">
            <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Contact Information</h3>
            <div className="space-y-0.5">
              <InfoItem label="Website" value={company.website} icon="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" link={company.website} />
              <InfoItem label="Email" value={company.email || company.official_email} icon="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              {company.sales_email && <InfoItem label="Sales Email" value={company.sales_email} icon="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />}
              <InfoItem label="Phone" value={company.phone || company.official_phone} icon="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              {company.whatsapp_business && <InfoItem label="WhatsApp" value={company.whatsapp_business} icon="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />}
              {company.linkedin_url && <InfoItem label="LinkedIn" value="View Profile" icon="M16 8a6 6 0 01-12 0 6 6 0 0112 0zM2 21a8 8 0 0116 0" link={company.linkedin_url} />}
            </div>
          </div>

          <div className="glass-card p-5">
            <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-3">Metadata</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Source</span><span className="text-gray-900 dark:text-white">{company.source || "-"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Crawl Date</span><span className="text-gray-900 dark:text-white">{company.crawl_date ? new Date(company.crawl_date).toLocaleDateString() : "-"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Enriched</span><span className="text-gray-900 dark:text-white">{company.enriched_at ? "Yes" : "No"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Lead Status</span><span className="text-gray-900 dark:text-white">{company.lead_status || "New"}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

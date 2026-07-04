import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { getIntelligence, analyzeCompany } from "../api/intelligence";

const OIL_LABELS = {
  palm_oil: { name: "Palm Oil", color: "bg-orange-500" },
  rbd_palm_olein: { name: "RBD Palm Olein", color: "bg-yellow-500" },
  sunflower_oil: { name: "Sunflower Oil", color: "bg-yellow-400" },
  soybean_oil: { name: "Soybean Oil", color: "bg-green-500" },
  rice_bran_oil: { name: "Rice Bran Oil", color: "bg-amber-500" },
  mustard_oil: { name: "Mustard Oil", color: "bg-yellow-600" },
  groundnut_oil: { name: "Groundnut Oil", color: "bg-amber-600" },
  coconut_oil: { name: "Coconut Oil", color: "bg-lime-500" },
  vanaspati: { name: "Vanaspati", color: "bg-gray-500" },
  shortening: { name: "Shortening", color: "bg-stone-500" },
  bakery_fat: { name: "Bakery Fat", color: "bg-rose-400" },
};

function Section({ title, icon, children }) {
  return (
    <div className="glass-card p-5">
      <div className="flex items-center gap-2 mb-4">
        {icon && <svg className="w-4 h-4 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} /></svg>}
        <h3 className="font-semibold text-gray-900 dark:text-white text-sm">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function ScoreGauge({ score, label, size = 100 }) {
  const r = size / 2 - 6;
  const s = 6;
  const nr = r - s;
  const c = nr * 2 * Math.PI;
  const offset = c - (score / 100) * c;
  const color = score >= 70 ? "#22c55e" : score >= 50 ? "#f59e0b" : score >= 30 ? "#f97316" : "#6b7280";
  return (
    <div className="relative inline-flex flex-col items-center">
      <div className="relative inline-flex items-center justify-center">
        <svg height={size} width={size}>
          <circle stroke="#e5e7eb" fill="transparent" strokeWidth={s} r={nr} cx={size / 2} cy={size / 2} className="dark:stroke-dark-700" />
          <circle stroke={color} fill="transparent" strokeWidth={s} strokeLinecap="round"
            strokeDasharray={c + " " + c} style={{ strokeDashoffset: offset, transition: "stroke-dashoffset 0.5s ease" }}
            r={nr} cx={size / 2} cy={size / 2} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
        </svg>
        <div className="absolute text-center">
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{score}</p>
          <p className="text-[10px] text-gray-500">/ 100</p>
        </div>
      </div>
      {label && <p className="text-xs text-gray-500 mt-1">{label}</p>}
    </div>
  );
}

function OilBar({ oilKey, probability }) {
  const oil = OIL_LABELS[oilKey] || { name: oilKey, color: "bg-gray-400" };
  const pct = Math.round(probability * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="w-32 text-xs text-gray-600 dark:text-gray-400">{oil.name}</span>
      <div className="flex-1 bg-gray-200 dark:bg-dark-700 rounded-full h-2.5">
        <div className={`${oil.color} h-2.5 rounded-full transition-all`} style={{ width: `${pct}%` }}></div>
      </div>
      <span className="w-10 text-xs font-medium text-gray-600 dark:text-gray-400 text-right">{pct}%</span>
    </div>
  );
}

function ScoreBar({ label, value, max = 100, color = "bg-brand-500" }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
        <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{value}/{max}</span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-dark-700 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${(value / max) * 100}%` }}></div>
      </div>
    </div>
  );
}

export default function IntelligenceDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    setLoading(true);
    getIntelligence(id)
      .then((r) => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      await analyzeCompany(id);
      setTimeout(async () => {
        const r = await getIntelligence(id);
        setData(r.data);
        setAnalyzing(false);
      }, 5000);
    } catch { setAnalyzing(false); }
  };

  if (loading) return (
    <div className="space-y-4">
      <div className="animate-pulse h-6 bg-gray-200 dark:bg-dark-700 rounded w-1/4"></div>
      <div className="grid grid-cols-3 gap-4">
        {Array(6).fill(0).map((_, i) => <div key={i} className="animate-pulse h-32 bg-gray-200 dark:bg-dark-700 rounded-xl"></div>)}
      </div>
    </div>
  );

  if (!data) return (
    <div className="text-center py-12">
      <p className="text-gray-500">Intelligence data not found</p>
      <Link to="/crm/intelligence" className="text-brand-600 hover:underline mt-4 inline-block">Back to Intelligence</Link>
    </div>
  );

  const { company, contacts, product_detection, buyer_score, summary } = data;
  const breakdown = buyer_score?.score_breakdown ? (typeof buyer_score.score_breakdown === "string" ? JSON.parse(buyer_score.score_breakdown) : buyer_score.score_breakdown) : {};

  return (
    <div className="animate-fade-in space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link to="/crm/intelligence" className="text-xs text-gray-500 hover:text-brand-600 inline-flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Back to Intelligence
          </Link>
          <div className="flex items-center gap-3 mt-2">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white text-xl font-bold">
              {company.name?.charAt(0)}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{company.name}</h1>
              <div className="flex items-center gap-2 mt-0.5">
                {company.industry && <span className="badge badge-info text-xs">{company.industry}</span>}
                {company.city && <span className="text-xs text-gray-500">{company.city}{company.state ? `, ${company.state}` : ""}</span>}
              </div>
            </div>
          </div>
        </div>
        <button onClick={handleAnalyze} disabled={analyzing}
          className="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-brand-500 to-brand-600 rounded-lg hover:from-brand-600 hover:to-brand-700 disabled:opacity-50 transition-all">
          {analyzing ? "Analyzing..." : "Re-analyze"}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-4">
          {/* Score Overview */}
          {buyer_score && (
            <Section title="Buyer Score" icon="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z">
              <div className="flex items-center gap-8 mb-6">
                <ScoreGauge score={buyer_score.buyer_score} label="Buyer Score" size={120} />
                <div className="flex-1 grid grid-cols-2 gap-4">
                  <div className="p-3 bg-gray-50 dark:bg-dark-900 rounded-lg text-center">
                    <p className="text-xl font-bold text-gray-900 dark:text-white">{buyer_score.buyer_priority}</p>
                    <p className="text-xs text-gray-500">Priority</p>
                  </div>
                  <div className="p-3 bg-gray-50 dark:bg-dark-900 rounded-lg text-center">
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{buyer_score.lead_temperature}</p>
                    <p className="text-xs text-gray-500">Temperature</p>
                  </div>
                  <div className="p-3 bg-gray-50 dark:bg-dark-900 rounded-lg text-center">
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{buyer_score.company_size}</p>
                    <p className="text-xs text-gray-500">Company Size</p>
                  </div>
                  <div className="p-3 bg-gray-50 dark:bg-dark-900 rounded-lg text-center">
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{buyer_score.procurement_maturity}</p>
                    <p className="text-xs text-gray-500">Maturity</p>
                  </div>
                </div>
              </div>

              {/* Consumption Details */}
              <div className="grid grid-cols-3 gap-4 p-4 bg-gray-50 dark:bg-dark-900 rounded-lg">
                <div>
                  <p className="text-xs text-gray-500 mb-1">Monthly Consumption</p>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{buyer_score.monthly_consumption || "Unknown"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Annual Consumption</p>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{buyer_score.annual_consumption || "Unknown"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Buying Frequency</p>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{buyer_score.buying_frequency || "Unknown"}</p>
                </div>
              </div>

              {/* Score Breakdown */}
              {Object.keys(breakdown).length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-3">Score Breakdown</p>
                  <div className="space-y-2">
                    <ScoreBar label="Industry" value={breakdown.industry || 0} max={25} color="bg-blue-500" />
                    <ScoreBar label="Oil Relevance" value={breakdown.oil_relevance || 0} max={25} color="bg-orange-500" />
                    <ScoreBar label="Company Size" value={breakdown.company_size || 0} max={15} color="bg-green-500" />
                    <ScoreBar label="Contacts" value={breakdown.contacts || 0} max={10} color="bg-purple-500" />
                    <ScoreBar label="Website" value={breakdown.website || 0} max={10} color="bg-cyan-500" />
                    <ScoreBar label="Completeness" value={breakdown.completeness || 0} max={10} color="bg-pink-500" />
                    <ScoreBar label="Existing Score" value={breakdown.existing || 0} max={5} color="bg-gray-400" />
                  </div>
                </div>
              )}
            </Section>
          )}

          {/* Product Detection */}
          {product_detection && (
            <Section title="Product Detection" icon="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4">
              <div className="space-y-2.5">
                {Object.entries(OIL_LABELS).map(([key, oil]) => (
                  <OilBar key={key} oilKey={key} probability={product_detection[key] || 0} />
                ))}
              </div>
              {product_detection.detection_notes && (
                <p className="mt-3 text-xs text-gray-500 dark:text-gray-400 italic">{product_detection.detection_notes}</p>
              )}
            </Section>
          )}

          {/* AI Summary */}
          {summary && (
            <Section title="AI Buyer Summary" icon="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z">
              <div className="space-y-4">
                <div className="p-4 bg-gray-50 dark:bg-dark-900 rounded-lg">
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Company Summary</p>
                  <p className="text-sm text-gray-700 dark:text-gray-300">{summary.company_summary}</p>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-dark-900 rounded-lg">
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Why This Buyer?</p>
                  <p className="text-sm text-gray-700 dark:text-gray-300">{summary.why_buyer}</p>
                </div>
                <div className="p-4 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
                  <p className="text-xs font-medium text-brand-600 dark:text-brand-400 mb-1">Recommended Pitch</p>
                  <p className="text-sm text-brand-700 dark:text-brand-300">{summary.recommended_pitch}</p>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-dark-900 rounded-lg">
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Suggested Products</p>
                  <div className="flex flex-wrap gap-1.5">
                    {(summary.suggested_products || []).map((p, i) => (
                      <span key={i} className="px-2.5 py-1 bg-brand-100 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400 rounded-full text-xs font-medium">{p}</span>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-gray-50 dark:bg-dark-900 rounded-lg">
                    <p className="text-xs font-medium text-gray-500 mb-1">Risk Level</p>
                    <p className={`text-sm font-bold ${summary.risk_level === "Low" ? "text-green-600" : summary.risk_level === "High" ? "text-red-600" : "text-yellow-600"}`}>{summary.risk_level}</p>
                  </div>
                  <div className="p-3 bg-gray-50 dark:bg-dark-900 rounded-lg">
                    <p className="text-xs font-medium text-gray-500 mb-1">Best First Contact</p>
                    <p className="text-sm text-gray-700 dark:text-gray-300">{summary.best_first_contact}</p>
                  </div>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-dark-900 rounded-lg">
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Follow-up Strategy</p>
                  <p className="text-sm text-gray-700 dark:text-gray-300">{summary.followup_strategy}</p>
                </div>
              </div>
            </Section>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Procurement Contacts */}
          <Section title={`Procurement Contacts (${contacts?.length || 0})`} icon="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z">
            {contacts?.length > 0 ? (
              <div className="space-y-2">
                {contacts.map((c, i) => (
                  <div key={i} className="p-3 bg-gray-50 dark:bg-dark-900 rounded-lg">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-xs font-bold">
                        {c.person_name?.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{c.person_name}</p>
                        <p className="text-xs text-gray-500 truncate">{c.designation || "Unknown role"}</p>
                      </div>
                    </div>
                    {c.email && <p className="text-xs text-brand-600 mt-1.5 truncate">{c.email}</p>}
                    {c.phone && <p className="text-xs text-gray-500 mt-0.5">{c.phone}</p>}
                    <div className="flex items-center justify-between mt-2">
                      <div className="w-16 bg-gray-200 dark:bg-dark-700 rounded-full h-1.5">
                        <div className={`h-1.5 rounded-full ${c.confidence_score >= 70 ? "bg-green-500" : c.confidence_score >= 40 ? "bg-yellow-500" : "bg-gray-400"}`} style={{ width: `${c.confidence_score}%` }}></div>
                      </div>
                      <span className="text-[10px] text-gray-400">{c.confidence_score}%</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400 text-center py-4">No contacts discovered yet</p>
            )}
          </Section>

          {/* Company Info */}
          <Section title="Company Info" icon="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Industry</span><span className="text-gray-900 dark:text-white">{company.industry || "-"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">City</span><span className="text-gray-900 dark:text-white">{company.city || "-"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">State</span><span className="text-gray-900 dark:text-white">{company.state || "-"}</span></div>
              {company.website && (
                <div className="pt-2 border-t border-gray-100 dark:border-dark-700">
                  <a href={company.website} target="_blank" rel="noreferrer" className="text-brand-600 hover:text-brand-700 text-xs">
                    Visit Website →
                  </a>
                </div>
              )}
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}

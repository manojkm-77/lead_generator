function ScoreBadge({ score }) {
  let color = "bg-gray-100 text-gray-800";
  let label = "Low";
  if (score >= 70) { color = "bg-green-100 text-green-800"; label = "High"; }
  else if (score >= 40) { color = "bg-yellow-100 text-yellow-800"; label = "Medium"; }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {score} - {label}
    </span>
  );
}

function ConfidenceBadge({ confidence }) {
  let color = "text-gray-500";
  if (confidence >= 70) color = "text-green-600";
  else if (confidence >= 40) color = "text-yellow-600";
  return <span className={`text-xs ${color}`}>{confidence}% confidence</span>;
}

function Section({ title, children }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
      {children}
    </div>
  );
}

function Field({ label, value, link, mailto, pre }) {
  if (!value) return (
    <div>
      <dt className="text-sm text-gray-500">{label}</dt>
      <dd className="mt-1 text-sm text-gray-400">-</dd>
    </div>
  );
  return (
    <div>
      <dt className="text-sm text-gray-500">{label}</dt>
      <dd className={`mt-1 text-sm text-gray-900 ${pre ? "whitespace-pre-wrap" : ""}`}>
        {mailto ? (
          <a href={`mailto:${value}`} className="text-primary-600 hover:underline">{value}</a>
        ) : link ? (
          <a href={value} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">{value}</a>
        ) : (
          value
        )}
      </dd>
    </div>
  );
}

export default function CompanyDetail({ company }) {
  if (!company) return null;

  const parseJson = (str) => {
    if (!str) return [];
    try { return JSON.parse(str); } catch { return [str]; }
  };

  const products = parseJson(company.products);
  const brands = parseJson(company.brands);
  const industries = parseJson(company.industries_served);

  return (
    <div className="space-y-6">
      {/* Basic Info */}
      <Section title={company.company_name}>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Website" value={company.website} link />
          <Field label="Phone" value={company.phone} />
          <Field label="WhatsApp" value={company.whatsapp} />
          <Field label="Email" value={company.email} mailto />
          <Field label="Address" value={company.address} />
          <Field label="City" value={company.city} />
          <Field label="State" value={company.state} />
          <Field label="Country" value={company.country} />
          <Field label="GST Number" value={company.gst_number} />
          <Field label="Source" value={company.source} />
          <Field label="Crawl Date" value={company.crawl_date} />
        </dl>
      </Section>

      {/* AI Lead Scoring */}
      <Section title="AI Lead Scoring">
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <dt className="text-sm text-gray-500">Industry</dt>
            <dd className="mt-1"><span className="px-2 py-1 bg-primary-50 text-primary-700 rounded text-sm">{company.industry || "Unknown"}</span></dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Lead Score</dt>
            <dd className="mt-1"><ScoreBadge score={company.lead_score || 0} /></dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Confidence</dt>
            <dd className="mt-1"><ConfidenceBadge confidence={company.ai_confidence || 0} /></dd>
          </div>
          <Field label="Reason" value={company.ai_reason} />
          <Field label="Estimated Size" value={company.estimated_size} />
          <Field label="Potential Oil Usage" value={company.potential_oil_usage} />
          <Field label="Est. Annual Consumption" value={company.estimated_annual_consumption || company.ai_consumption} />
          <Field label="Buying Frequency" value={company.ai_frequency} />
        </dl>
      </Section>

      {/* Website Enrichment */}
      {(company.about_us || company.company_description || products.length > 0 || brands.length > 0) && (
        <Section title="Website Enrichment">
          <dl className="space-y-4">
            {company.company_description && (
              <Field label="Description" value={company.company_description} />
            )}
            {company.about_us && (
              <Field label="About Us" value={company.about_us} pre />
            )}
            {products.length > 0 && (
              <div>
                <dt className="text-sm text-gray-500">Products</dt>
                <dd className="mt-1 flex flex-wrap gap-2">
                  {products.map((p, i) => (
                    <span key={i} className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">{p}</span>
                  ))}
                </dd>
              </div>
            )}
            {brands.length > 0 && (
              <div>
                <dt className="text-sm text-gray-500">Brands</dt>
                <dd className="mt-1 flex flex-wrap gap-2">
                  {brands.map((b, i) => (
                    <span key={i} className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs">{b}</span>
                  ))}
                </dd>
              </div>
            )}
            {industries.length > 0 && (
              <div>
                <dt className="text-sm text-gray-500">Industries Served</dt>
                <dd className="mt-1 flex flex-wrap gap-2">
                  {industries.map((ind, i) => (
                    <span key={i} className="px-2 py-1 bg-green-50 text-green-700 rounded text-xs">{ind}</span>
                  ))}
                </dd>
              </div>
            )}
          </dl>
        </Section>
      )}

      {/* Procurement & Careers */}
      {(company.procurement_info || company.contact_page || company.careers_page) && (
        <Section title="Procurement & Careers">
          <dl className="space-y-4">
            <Field label="Contact Page" value={company.contact_page} link />
            <Field label="Careers Page" value={company.careers_page} link />
            {company.procurement_info && (
              <Field label="Procurement Info" value={company.procurement_info} pre />
            )}
          </dl>
        </Section>
      )}

      {/* Enrichment Status */}
      {company.enriched_at && (
        <div className="text-xs text-gray-400 text-right">
          Enriched: {new Date(company.enriched_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

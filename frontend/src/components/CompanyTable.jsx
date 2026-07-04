import { Link } from "react-router-dom";

function ScoreBadge({ score }) {
  let color = "bg-gray-100 text-gray-800";
  if (score >= 70) color = "bg-green-100 text-green-800";
  else if (score >= 40) color = "bg-yellow-100 text-yellow-800";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {score}
    </span>
  );
}

function ContactBadges({ company }) {
  return (
    <div className="flex gap-1">
      {company.email && <span className="px-1.5 py-0.5 rounded text-xs bg-blue-50 text-blue-600" title={company.email}>E</span>}
      {company.phone && <span className="px-1.5 py-0.5 rounded text-xs bg-green-50 text-green-600" title={company.phone}>P</span>}
      {company.website && <span className="px-1.5 py-0.5 rounded text-xs bg-purple-50 text-purple-600" title={company.website}>W</span>}
    </div>
  );
}

export default function CompanyTable({ companies, onConvert }) {
  if (!companies?.length) {
    return (
      <div className="bg-white rounded-lg shadow-sm border p-12 text-center text-gray-500">
        No companies found
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {["Company", "Location", "Industry", "Score", "Contacts", "Source", "Action"].map((h) => (
              <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {companies.map((c) => (
            <tr key={c.id} className="hover:bg-gray-50">
              <td className="px-4 py-3">
                <Link to={`/company/${c.id}`} className="text-primary-600 hover:underline font-medium text-sm">{c.company_name}</Link>
                {c.phone && <p className="text-xs text-gray-400 mt-0.5">{c.phone}</p>}
              </td>
              <td className="px-4 py-3 text-sm text-gray-500">
                {c.city || "-"}{c.state && <span className="text-gray-400">, {c.state}</span>}
              </td>
              <td className="px-4 py-3 text-sm text-gray-500">{c.industry || "-"}</td>
              <td className="px-4 py-3"><ScoreBadge score={c.lead_score} /></td>
              <td className="px-4 py-3"><ContactBadges company={c} /></td>
              <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">{c.source || "-"}</span></td>
              <td className="px-4 py-3">
                {onConvert && (
                  <button onClick={() => onConvert(c.id)} className="text-xs text-primary-600 hover:underline">
                    + Lead
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

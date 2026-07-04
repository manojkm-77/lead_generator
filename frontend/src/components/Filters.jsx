const SOURCES = [
  { value: "", label: "All Sources" },
  { value: "indiamart", label: "IndiaMART" },
  { value: "justdial", label: "JustDial" },
  { value: "tradeindia", label: "TradeIndia" },
  { value: "yellowpages", label: "Yellow Pages" },
  { value: "exportersindia", label: "ExportersIndia" },
  { value: "companywebsite", label: "Company Website" },
  { value: "tradeassociation", label: "Trade Association" },
  { value: "gst_directory", label: "GST Directory" },
  { value: "tradeexhibition", label: "Trade Exhibition" },
  { value: "googlemaps", label: "Google Maps" },
  { value: "linkedin", label: "LinkedIn" },
];

export default function Filters({ filters, onChange }) {
  const input = "border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500";
  const select = `${input} bg-white`;

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4 mb-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <input
          className={input}
          placeholder="Search company..."
          value={filters.search || ""}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
        />
        <input
          className={input}
          placeholder="City"
          value={filters.city || ""}
          onChange={(e) => onChange({ ...filters, city: e.target.value })}
        />
        <input
          className={input}
          placeholder="Industry"
          value={filters.industry || ""}
          onChange={(e) => onChange({ ...filters, industry: e.target.value })}
        />
        <select
          className={select}
          value={filters.source || ""}
          onChange={(e) => onChange({ ...filters, source: e.target.value })}
        >
          {SOURCES.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <input
          className={input}
          type="number"
          placeholder="Min Score"
          min={0}
          max={100}
          value={filters.min_score || ""}
          onChange={(e) => onChange({ ...filters, min_score: e.target.value })}
        />
        <div className="flex gap-2">
          <label className="flex items-center gap-1 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={filters.has_email || false}
              onChange={(e) => onChange({ ...filters, has_email: e.target.checked })}
              className="rounded"
            />
            Has Email
          </label>
          <label className="flex items-center gap-1 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={filters.has_phone || false}
              onChange={(e) => onChange({ ...filters, has_phone: e.target.checked })}
              className="rounded"
            />
            Has Phone
          </label>
        </div>
      </div>
    </div>
  );
}

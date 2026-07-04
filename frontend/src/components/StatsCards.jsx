const icons = {
  companies: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
  leads: "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6",
  quality: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  email: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
  phone: "M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z",
  website: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9",
  cities: "M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z",
  states: "M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064",
  countries: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9",
};

function Card({ title, value, icon, color = "primary" }) {
  const colorMap = {
    primary: "bg-primary-50 text-primary-600",
    green: "bg-green-50 text-green-600",
    yellow: "bg-yellow-50 text-yellow-600",
    purple: "bg-purple-50 text-purple-600",
    blue: "bg-blue-50 text-blue-600",
    indigo: "bg-indigo-50 text-indigo-600",
    pink: "bg-pink-50 text-pink-600",
    orange: "bg-orange-50 text-orange-600",
  };
  return (
    <div className="bg-white rounded-lg shadow-sm border p-6">
      <div className="flex items-center">
        <div className={`p-3 rounded-lg ${colorMap[color]}`}>
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icons[icon]} />
          </svg>
        </div>
        <div className="ml-4">
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-semibold text-gray-900">{value ?? "..."}</p>
        </div>
      </div>
    </div>
  );
}

export default function StatsCards({ stats }) {
  if (!stats) return null;
  const cards = [
    { title: "Total Companies", value: stats.total_companies, icon: "companies", color: "primary" },
    { title: "New Today", value: stats.today_new_leads, icon: "leads", color: "green" },
    { title: "High Quality", value: stats.high_quality_leads, icon: "quality", color: "yellow" },
    { title: "Emails Found", value: stats.emails_found, icon: "email", color: "blue" },
    { title: "Phones Found", value: stats.phones_found, icon: "phone", color: "purple" },
    { title: "Websites Found", value: stats.websites_found, icon: "website", color: "indigo" },
    { title: "Cities", value: stats.cities, icon: "cities", color: "pink" },
    { title: "States", value: stats.states, icon: "states", color: "orange" },
  ];
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {cards.map((c) => (
        <Card key={c.title} {...c} />
      ))}
    </div>
  );
}

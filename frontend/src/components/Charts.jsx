import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];

function ChartCard({ title, children }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border p-6">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      {children}
    </div>
  );
}

export function SourceBreakdown({ data }) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <ChartCard title="Sources">
        <p className="text-gray-500 text-center py-8">No data yet</p>
      </ChartCard>
    );
  }
  const chartData = Object.entries(data).map(([name, value]) => ({ name, value }));
  return (
    <ChartCard title="Leads by Source">
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie data={chartData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
            {chartData.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function IndustryBreakdown({ data }) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <ChartCard title="Industries">
        <p className="text-gray-500 text-center py-8">No data yet</p>
      </ChartCard>
    );
  }
  const chartData = Object.entries(data).map(([name, value]) => ({ name, value }));
  return (
    <ChartCard title="Top Industries">
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function RecentActivity({ data }) {
  if (!data || data.length === 0) {
    return (
      <ChartCard title="Recent Activity">
        <p className="text-gray-500 text-center py-8">No data yet</p>
      </ChartCard>
    );
  }
  return (
    <ChartCard title="Last 7 Days">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis />
          <Tooltip />
          <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

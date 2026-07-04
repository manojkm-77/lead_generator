import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export default function ScoreDistribution({ distribution }) {
  const data = distribution
    ? Object.entries(distribution).map(([range, count]) => ({ range, count }))
    : []

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-lg font-semibold mb-4">Lead Score Distribution</h3>
      {data.length > 0 ? (
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="range" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#3B82F6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-gray-400 text-center py-8">No data yet</p>
      )}
    </div>
  )
}

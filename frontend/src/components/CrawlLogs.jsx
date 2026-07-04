import { useState, useEffect } from 'react'
import { getCrawlLogs } from '../api/client'

export default function CrawlLogs() {
  const [logs, setLogs] = useState([])

  useEffect(() => {
    getCrawlLogs({ limit: 10 }).then(({ data }) => setLogs(data))
  }, [])

  if (!logs.length) {
    return <p className="text-gray-500 text-center py-8">No crawl logs yet</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Spider</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Status</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Started</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Found</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-gray-500">Dupes</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id} className="border-b border-gray-100">
              <td className="px-4 py-3 text-sm">{log.spider_name}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                  log.status === 'completed' ? 'bg-green-100 text-green-800' :
                  log.status === 'failed' ? 'bg-red-100 text-red-800' :
                  'bg-yellow-100 text-yellow-800'
                }`}>
                  {log.status}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">
                {new Date(log.start_time).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-sm">{log.companies_found}</td>
              <td className="px-4 py-3 text-sm">{log.duplicates_removed}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

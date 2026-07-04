import { Download, FileSpreadsheet, FileJson, Database } from 'lucide-react'
import { exportData } from '../api/client'

export default function ExportButtons() {
  const handleExport = async (format) => {
    try {
      const { data } = await exportData({ format })
      alert(`Exported ${data.count} companies to ${data.filepath}`)
    } catch (err) {
      console.error('Export failed:', err)
    }
  }

  const buttons = [
    { format: 'csv', icon: Download, label: 'CSV' },
    { format: 'excel', icon: FileSpreadsheet, label: 'Excel' },
    { format: 'json', icon: FileJson, label: 'JSON' },
  ]

  return (
    <div className="flex gap-2">
      {buttons.map(({ format, icon: Icon, label }) => (
        <button
          key={format}
          onClick={() => handleExport(format)}
          className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors"
        >
          <Icon className="w-4 h-4" />
          {label}
        </button>
      ))}
    </div>
  )
}

// PATH: src/components/AdminPanel.tsx

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import api from '../api/axios'

interface SystemStatus {
  redis_stats: {
    connected_clients: number
    used_memory: string
    total_commands_processed: number
  }
  disk_usage: {
    total: string
    used: string
    free: string
  }
}

export function AdminPanel() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)

  useEffect(() => {
    fetchSystemStatus()
  }, [])

  const fetchSystemStatus = async () => {
    try {
      const response = await api.get('/api/v1/admin/system/status')
      setSystemStatus(response.data)
    } catch (error) {
      console.error('System status fetch error:', error)
      // TODO: Add error handling
    }
  }

  if (!systemStatus) {
    return <div>Loading...</div>
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle>Redis Stats</CardTitle>
        </CardHeader>
        <CardContent>
          <p>Connected Clients: {systemStatus.redis_stats.connected_clients}</p>
          <p>Used Memory: {systemStatus.redis_stats.used_memory}</p>
          <p>Total Commands Processed: {systemStatus.redis_stats.total_commands_processed}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Disk Usage</CardTitle>
        </CardHeader>
        <CardContent>
          <p>Total: {systemStatus.disk_usage.total}</p>
          <p>Used: {systemStatus.disk_usage.used}</p>
          <p>Free: {systemStatus.disk_usage.free}</p>
        </CardContent>
      </Card>
    </div>
  )
}

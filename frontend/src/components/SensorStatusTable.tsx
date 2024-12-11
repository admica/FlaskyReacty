// PATH: src/components/SensorStatusTable.tsx

import { useEffect, useState } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import api from '../api/axios'

interface Sensor {
  name: string
  status: string
  last_update: string
}

export function SensorStatusTable() {
  const [sensors, setSensors] = useState<Sensor[]>([])

  useEffect(() => {
    fetchSensors()
  }, [])

  const fetchSensors = async () => {
    try {
      const response = await api.get('/api/v1/sensors')
      setSensors(response.data)
    } catch (error) {
      console.error('Sensor status fetch error:', error)
      // TODO: Add error handling
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Last Update</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sensors.map((sensor) => (
          <TableRow key={sensor.name}>
            <TableCell>{sensor.name}</TableCell>
            <TableCell>{sensor.status}</TableCell>
            <TableCell>{new Date(sensor.last_update).toLocaleString()}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

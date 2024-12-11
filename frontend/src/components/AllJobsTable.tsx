// PATH: src/components/AllJobsTable.tsx

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

interface Job {
  id: number
  username: string
  sensor: string
  status: string
  start_time: string
  end_time: string
}

export function AllJobsTable() {
  const [jobs, setJobs] = useState<Job[]>([])

  useEffect(() => {
    fetchJobs()
  }, [])

  const fetchJobs = async () => {
    try {
      const response = await api.get('/api/v1/jobs/all')
      setJobs(response.data)
    } catch (error) {
      console.error('All jobs fetch error:', error)
      // TODO: Add error handling
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Username</TableHead>
          <TableHead>Sensor</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Start Time</TableHead>
          <TableHead>End Time</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {jobs.map((job) => (
          <TableRow key={job.id}>
            <TableCell>{job.id}</TableCell>
            <TableCell>{job.username}</TableCell>
            <TableCell>{job.sensor}</TableCell>
            <TableCell>{job.status}</TableCell>
            <TableCell>{new Date(job.start_time).toLocaleString()}</TableCell>
            <TableCell>{new Date(job.end_time).toLocaleString()}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

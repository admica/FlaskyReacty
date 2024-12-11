// PATH: src/components/JobHistory.tsx

import { useEffect, useState } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import api from '../api/axios'

interface Job {
  id: number
  sensor: string
  status: string
  start_time: string
  end_time: string
}

export function JobHistory() {
  const [jobs, setJobs] = useState<Job[]>([])

  useEffect(() => {
    fetchJobs()
  }, [])

  const fetchJobs = async () => {
    try {
      const response = await api.get('/api/v1/jobs')
      setJobs(response.data)
    } catch (error) {
      console.error('Job history fetch error:', error)
      // TODO: Add error handling
    }
  }

  const handleCancel = async (jobId: number) => {
    try {
      await api.post(`/api/v1/jobs/${jobId}/cancel`)
      fetchJobs() // Refresh job list
    } catch (error) {
      console.error('Job cancellation error:', error)
      // TODO: Add error handling
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Sensor</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Start Time</TableHead>
          <TableHead>End Time</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {jobs.map((job) => (
          <TableRow key={job.id}>
            <TableCell>{job.id}</TableCell>
            <TableCell>{job.sensor}</TableCell>
            <TableCell>{job.status}</TableCell>
            <TableCell>{new Date(job.start_time).toLocaleString()}</TableCell>
            <TableCell>{new Date(job.end_time).toLocaleString()}</TableCell>
            <TableCell>
              <Button
                onClick={() => handleCancel(job.id)}
                disabled={job.status !== "Processing"}
              >
                Cancel
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

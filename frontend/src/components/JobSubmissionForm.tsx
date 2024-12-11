// PATH: src/components/JobSubmissionForm.tsx

import { useState, FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import api from '../api/axios'

export function JobSubmissionForm() {
  const [sensor, setSensor] = useState("")
  const [srcIp, setSrcIp] = useState("")
  const [dstIp, setDstIp] = useState("")
  const [startTime, setStartTime] = useState("")
  const [endTime, setEndTime] = useState("")
  const [description, setDescription] = useState("")

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    try {
      const response = await api.post('/api/v1/jobs', {
        sensor,
        srcIp,
        dstIp,
        startTime,
        endTime,
        description
      })
      console.log('Job submitted:', response.data)
      // TODO: Add success notification
    } catch (error) {
      console.error('Job submission failed:', error)
      // TODO: Add error notification
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <Card>
        <CardHeader>
          <CardTitle>Submit New Job</CardTitle>
          <CardDescription>
            Create a new PCAP analysis job by providing the required parameters.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="sensor">Sensor</Label>
            <Input
              id="sensor"
              value={sensor}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSensor(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="srcIp">Source IP</Label>
            <Input
              id="srcIp"
              value={srcIp}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSrcIp(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="dstIp">Destination IP</Label>
            <Input
              id="dstIp"
              value={dstIp}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDstIp(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="startTime">Start Time</Label>
            <Input
              id="startTime"
              type="datetime-local"
              value={startTime}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setStartTime(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="endTime">End Time</Label>
            <Input
              id="endTime"
              type="datetime-local"
              value={endTime}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEndTime(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDescription(e.target.value)}
              required
            />
          </div>
        </CardContent>
        <CardFooter>
          <Button type="submit">Submit Job</Button>
        </CardFooter>
      </Card>
    </form>
  )
}

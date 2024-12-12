// PATH: src/components/JobSubmissionForm.tsx

import { useState, FormEvent, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import api from '../api/axios'

interface Sensor {
  name: string
  status: string
  location: string
}

export function JobSubmissionForm() {
  const [selectedLocation, setSelectedLocation] = useState<string>("")
  const [availableLocations, setAvailableLocations] = useState<string[]>([])
  const [srcIp, setSrcIp] = useState("")
  const [dstIp, setDstIp] = useState("")
  const [startTime, setStartTime] = useState("")
  const [endTime, setEndTime] = useState("")
  const [description, setDescription] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const loadLocations = async () => {
      try {
        const response = await api.get('/api/v1/sensors')
        // Extract unique locations from sensors
        const locations = [...new Set(response.data.sensors.map((sensor: Sensor) => sensor.location))]
        setAvailableLocations(locations.filter(Boolean).sort()) // Remove empty locations and sort
      } catch (error) {
        console.error('Failed to load locations:', error)
      }
    }
    loadLocations()
  }, [])

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLoading(true)
    try {
      const response = await api.post('/api/v1/jobs', {
        location: selectedLocation,
        srcIp,
        dstIp,
        startTime,
        endTime,
        description
      })
      console.log('Job submitted:', response.data)
      // Reset form
      setSelectedLocation("")
      setSrcIp("")
      setDstIp("")
      setStartTime("")
      setEndTime("")
      setDescription("")
      // TODO: Add success notification
    } catch (error) {
      console.error('Job submission failed:', error)
      // TODO: Add error notification
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <Card>
        <CardHeader>
          <CardTitle>Submit New Job</CardTitle>
          <CardDescription>
            Create a new PCAP analysis job by selecting a location and providing the required parameters.
            The job will be executed on all sensors at the selected location.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="location">Location</Label>
            <select
              id="location"
              value={selectedLocation}
              onChange={(e) => setSelectedLocation(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              required
            >
              <option value="">Select a location...</option>
              {availableLocations.map((location) => (
                <option key={location} value={location}>
                  {location}
                </option>
              ))}
            </select>
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
          <Button type="submit" disabled={loading}>
            {loading ? "Submitting..." : "Submit Job"}
          </Button>
        </CardFooter>
      </Card>
    </form>
  )
}

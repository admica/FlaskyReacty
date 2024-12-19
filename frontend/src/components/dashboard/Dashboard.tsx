// PATH: src/components/dashboard/Dashboard.tsx

import { useState, useEffect } from 'react';
import {
  Container,
  Paper,
  Title,
  Text,
  Badge,
  Group,
  Stack,
  Button,
  Table,
  Alert,
  LoadingOverlay,
  TextInput,
  Select,
  Grid,
  Modal,
  ScrollArea,
  Box,
  Code,
} from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { IconAlertCircle, IconRefresh } from '@tabler/icons-react';
import apiService from '../../services/api';
import type { Job, Sensor, Task } from '../../services/api';

export function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [locations, setLocations] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [formData, setFormData] = useState({
    location: '',
    description: '',
    src_ip: '',
    dst_ip: '',
    event_time: null as Date | null,
    start_time: null as Date | null,
    end_time: null as Date | null,
    timezone: 'UTC'  // Default to UTC
  });

  // Common timezone options
  const timezoneOptions = [
    { value: 'UTC', label: 'UTC' },
    { value: 'America/New_York', label: 'Eastern Time (ET)' },
    { value: 'America/Chicago', label: 'Central Time (CT)' },
    { value: 'America/Denver', label: 'Mountain Time (MT)' },
    { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
    { value: 'America/Anchorage', label: 'Alaska Time (AKT)' },
    { value: 'Pacific/Honolulu', label: 'Hawaii Time (HT)' }
  ];

  const loadJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('Fetching jobs...');
      const response = await apiService.getJobs();
      console.log('Jobs response:', response);
      setJobs(response);
    } catch (err: any) {
      console.error('Error loading jobs:', err);
      setError(err.message || 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  const loadLocations = async () => {
    try {
      const response = await apiService.getSensors();
      const uniqueLocations = [...new Set(response.sensors
        .map((sensor: Sensor) => sensor.location)
        .filter(Boolean)
      )].sort();
      setLocations(uniqueLocations);
    } catch (err: any) {
      console.error('Error loading locations:', err);
      setError(err.message || 'Failed to load locations');
    }
  };

  useEffect(() => {
    loadJobs();
    loadLocations();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);

      // Validate required fields
      if (!formData.location) {
        setError('Location is required');
        return;
      }
      if (!formData.src_ip && !formData.dst_ip) {
        setError('At least one IP address is required');
        return;
      }
      if (!formData.event_time && (!formData.start_time || !formData.end_time)) {
        setError('Either Event Time or both Start Time and End Time are required');
        return;
      }

      // Format the job data to match API expectations
      const jobData = {
        location: formData.location.toUpperCase(),
        params: {
          description: formData.description || undefined,
          src_ip: formData.src_ip || undefined,
          dst_ip: formData.dst_ip || undefined,
          event_time: formData.event_time ? formData.event_time.toISOString() + "Z" : undefined,
          start_time: formData.start_time ? formData.start_time.toISOString() + "Z" : undefined,
          end_time: formData.end_time ? formData.end_time.toISOString() + "Z" : undefined,
          tz: formData.timezone
        }
      };

      // Submit the job
      const result = await apiService.submitJob(jobData);
      console.log('Job submitted successfully:', result);
      
      // Clear form
      setFormData({
        location: '',
        description: '',
        src_ip: '',
        dst_ip: '',
        event_time: null,
        start_time: null,
        end_time: null,
        timezone: 'UTC'
      });

      // Refresh jobs list
      await loadJobs();

    } catch (err: any) {
      console.error('Error submitting job:', err);
      setError(err.message || 'Failed to submit job');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'Running': 'blue',
      'Complete': 'green',
      'Failed': 'red',
      'Submitted': 'yellow',
      'Cancelled': 'gray',
      'Retrieving': 'violet',
      'Completed': 'green',
      'Merging': 'indigo',
      'Partially Complete': 'orange',
    };
    return colors[status] || 'gray';
  };

  const formatDateTime = (date: string | null) => {
    if (!date) return '-';
    return new Date(date).toLocaleString();
  };

  const formatSize = (size: string | null) => {
    if (!size) return '-';
    const num = parseInt(size);
    if (isNaN(num)) return size;
    
    const units = ['B', 'KB', 'MB', 'GB'];
    let unitIndex = 0;
    let value = num;

    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex++;
    }

    return `${value.toFixed(1)} ${units[unitIndex]}`;
  };

  const formatMessage = (message: string | null) => {
    if (!message) return '-';
    try {
      // Try to parse as JSON
      const parsed = JSON.parse(message);
      // Convert the parsed object into a list of key-value pairs
      return (
        <Stack gap={2}>
          {Object.entries(parsed).map(([key, value]) => (
            <Group key={key} gap="xs">
              <Text size="sm" fw={500} style={{ textTransform: 'capitalize' }}>
                {key.replace(/_/g, ' ')}:
              </Text>
              <Text size="sm">
                {typeof value === 'boolean' ? value.toString() : String(value)}
              </Text>
            </Group>
          ))}
        </Stack>
      );
    } catch {
      // If not JSON, return as is
      return message;
    }
  };

  return (
    <Box p="md">
      <Stack gap="md">
        <Group justify="space-between" align="center">
          <Title order={2}>Dashboard</Title>
          <Button 
            leftSection={<IconRefresh size={16} />}
            onClick={loadJobs}
            loading={loading}
          >
            Refresh
          </Button>
        </Group>

        {error && (
          <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
            {error}
          </Alert>
        )}

        {/* Job Submission Form */}
        <Paper withBorder p="md">
          <form onSubmit={handleSubmit}>
            <Stack gap="md">
              <Title order={3}>Submit New Job</Title>

              <Grid>
                <Grid.Col span={3}>
                  <Select
                    label="Location"
                    placeholder="Select location"
                    data={locations}
                    value={formData.location}
                    onChange={(value) => setFormData(prev => ({ ...prev, location: value || '' }))}
                    required
                  />
                </Grid.Col>
                <Grid.Col span={9}>
                  <TextInput
                    label="Description"
                    placeholder="Job description"
                    value={formData.description}
                    onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  />
                </Grid.Col>
                <Grid.Col span={3}>
                  <DateTimePicker
                    label="Event Time (Optional)"
                    placeholder="Select event time"
                    value={formData.event_time}
                    onChange={(value) => setFormData(prev => ({ ...prev, event_time: value }))}
                    clearable
                    withSeconds
                  />
                </Grid.Col>
                <Grid.Col span={3}>
                  <DateTimePicker
                    label="Start Time"
                    placeholder="Select start time"
                    value={formData.start_time}
                    onChange={(value) => setFormData(prev => ({ ...prev, start_time: value }))}
                    required={!formData.event_time}
                    disabled={!!formData.event_time}
                    clearable
                    withSeconds
                  />
                </Grid.Col>
                <Grid.Col span={3}>
                  <DateTimePicker
                    label="End Time"
                    placeholder="Select end time"
                    value={formData.end_time}
                    onChange={(value) => setFormData(prev => ({ ...prev, end_time: value }))}
                    required={!formData.event_time}
                    disabled={!!formData.event_time}
                    clearable
                    withSeconds
                  />
                </Grid.Col>
                <Grid.Col span={3}>
                  <Select
                    label="Timezone"
                    placeholder="Select timezone"
                    value={formData.timezone}
                    onChange={(value) => setFormData(prev => ({ ...prev, timezone: value || 'UTC' }))}
                    data={timezoneOptions}
                    searchable
                  />
                </Grid.Col>
                <Grid.Col span={3}>
                  <TextInput
                    label="Source IP"
                    placeholder="Enter source IP"
                    value={formData.src_ip}
                    onChange={(e) => setFormData(prev => ({ ...prev, src_ip: e.target.value }))}
                  />
                </Grid.Col>
                <Grid.Col span={3}>
                  <TextInput
                    label="Destination IP"
                    placeholder="Enter destination IP"
                    value={formData.dst_ip}
                    onChange={(e) => setFormData(prev => ({ ...prev, dst_ip: e.target.value }))}
                  />
                </Grid.Col>
                <Grid.Col span={6} style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end' }}>
                  <Button 
                    type="submit" 
                    loading={submitting}
                    disabled={!formData.location || (!formData.src_ip && !formData.dst_ip)}
                  >
                    Submit Job
                  </Button>
                </Grid.Col>
              </Grid>
            </Stack>
          </form>
        </Paper>

        {/* Jobs List */}
        <Paper pos="relative" p="md" withBorder>
          <LoadingOverlay visible={loading} />
          
          <Stack gap="md">
            <Title order={3}>Recent Jobs</Title>

            {jobs.length === 0 ? (
              <Text c="dimmed">No jobs found</Text>
            ) : (
              <ScrollArea>
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>ID</Table.Th>
                      <Table.Th style={{ width: '120px' }}>Status</Table.Th>
                      <Table.Th>Description</Table.Th>
                      <Table.Th>Location</Table.Th>
                      <Table.Th>Source IP</Table.Th>
                      <Table.Th>Destination IP</Table.Th>
                      <Table.Th>Started</Table.Th>
                      <Table.Th>Completed</Table.Th>
                      <Table.Th>Result Size</Table.Th>
                      <Table.Th>Message</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {jobs.map((job) => (
                      <Table.Tr 
                        key={job.id} 
                        style={{ cursor: 'pointer' }}
                        onClick={() => setSelectedJob(job)}
                      >
                        <Table.Td>{job.id}</Table.Td>
                        <Table.Td style={{ width: '120px' }}>
                          <Badge 
                            color={getStatusColor(job.status)}
                            style={{ minWidth: '100px', textAlign: 'center' }}
                          >
                            {job.status}
                          </Badge>
                        </Table.Td>
                        <Table.Td>{job.description}</Table.Td>
                        <Table.Td>{job.location}</Table.Td>
                        <Table.Td>{job.src_ip || '-'}</Table.Td>
                        <Table.Td>{job.dst_ip || '-'}</Table.Td>
                        <Table.Td>{formatDateTime(job.started_at)}</Table.Td>
                        <Table.Td>{formatDateTime(job.completed_at)}</Table.Td>
                        <Table.Td>{formatSize(job.result_size)}</Table.Td>
                        <Table.Td>{job.result_message || '-'}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </ScrollArea>
            )}
          </Stack>
        </Paper>

        {/* Task Details Modal */}
        <Modal
          opened={!!selectedJob}
          onClose={() => setSelectedJob(null)}
          title={<Title order={3}>Job {selectedJob?.id} Details</Title>}
          size="90%"
          styles={{
            body: {
              minWidth: '1000px'  // Ensures a minimum width
            }
          }}
        >
          {selectedJob && (
            <Stack gap="md">
              <Group>
                <Badge color={getStatusColor(selectedJob.status)}>
                  {selectedJob.status}
                </Badge>
                <Text size="sm">{selectedJob.description}</Text>
              </Group>

              {/* Job Details */}
              <Paper withBorder p="md">
                <Title order={4} mb="md">Job Information</Title>
                <Grid>
                  <Grid.Col span={6}>
                    <Stack gap="xs">
                      <Group>
                        <Text fw={500}>Location:</Text>
                        <Text>{selectedJob.location}</Text>
                      </Group>
                      <Group>
                        <Text fw={500}>Source IP:</Text>
                        <Text>{selectedJob.src_ip || '-'}</Text>
                      </Group>
                      <Group>
                        <Text fw={500}>Destination IP:</Text>
                        <Text>{selectedJob.dst_ip || '-'}</Text>
                      </Group>
                      <Group>
                        <Text fw={500}>Event Time:</Text>
                        <Text>{formatDateTime(selectedJob.event_time)}</Text>
                      </Group>
                    </Stack>
                  </Grid.Col>
                  <Grid.Col span={6}>
                    <Stack gap="xs">
                      <Group>
                        <Text fw={500}>Start Time:</Text>
                        <Text>{formatDateTime(selectedJob.start_time)}</Text>
                      </Group>
                      <Group>
                        <Text fw={500}>End Time:</Text>
                        <Text>{formatDateTime(selectedJob.end_time)}</Text>
                      </Group>
                      <Group>
                        <Text fw={500}>Created:</Text>
                        <Text>{formatDateTime(selectedJob.created_at)}</Text>
                      </Group>
                      <Group>
                        <Text fw={500}>Result Size:</Text>
                        <Text>{formatSize(selectedJob.result_size)}</Text>
                      </Group>
                    </Stack>
                  </Grid.Col>
                </Grid>
              </Paper>

              {/* Tasks List */}
              <Paper withBorder p="md">
                <Title order={4} mb="md">Tasks</Title>
                {selectedJob.tasks?.length ? (
                  <Table striped highlightOnHover>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Task ID</Table.Th>
                        <Table.Th>Sensor</Table.Th>
                        <Table.Th style={{ width: '120px' }}>Status</Table.Th>
                        <Table.Th>Created</Table.Th>
                        <Table.Th>Started</Table.Th>
                        <Table.Th>Completed</Table.Th>
                        <Table.Th>Size</Table.Th>
                        <Table.Th>Message</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {selectedJob.tasks.map((task) => (
                        <Table.Tr key={task.id}>
                          <Table.Td>{task.task_id}</Table.Td>
                          <Table.Td>{task.sensor}</Table.Td>
                          <Table.Td style={{ width: '120px' }}>
                            <Badge 
                              color={getStatusColor(task.status)}
                              style={{ minWidth: '100px', textAlign: 'center' }}
                            >
                              {task.status}
                            </Badge>
                          </Table.Td>
                          <Table.Td>{formatDateTime(task.created_at)}</Table.Td>
                          <Table.Td>{formatDateTime(task.started_at)}</Table.Td>
                          <Table.Td>{formatDateTime(task.completed_at)}</Table.Td>
                          <Table.Td>{formatSize(task.pcap_size)}</Table.Td>
                          <Table.Td style={{ maxWidth: '400px' }}>
                            {formatMessage(task.result_message)}
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                ) : (
                  <Text c="dimmed">No tasks found for this job</Text>
                )}
              </Paper>
            </Stack>
          )}
        </Modal>
      </Stack>
    </Box>
  );
} 
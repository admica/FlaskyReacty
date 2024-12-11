// PATH: src/components/dashboard/Dashboard.tsx

import { useState, useEffect, useRef } from 'react';
import {
  TextInput,
  Button,
  Paper,
  Title,
  Table,
  Text,
  Badge,
  Group,
  Stack,
  Select,
  Grid,
  Alert,
  ActionIcon,
  ScrollArea,
} from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { IconAlertCircle, IconTrash, IconPlayerStop, IconFileAnalytics } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useModals } from '@mantine/modals';
import apiService from '../../services/api';

interface Task {
  id: number;
  sensor: string;
  status: string;
  started: string | null;
  completed: string | null;
  result_message?: string;
}

interface Job {
  id: number;
  username: string;
  status: string;
  description: string;
  location: string;
  src_ip: string | null;
  dst_ip: string | null;
  event_time: string | null;
  start_time: string;
  end_time: string;
  started: string | null;
  completed: string | null;
  result: string | null;
  filename: string | null;
  analysis: string | null;
  tz: string;
  tasks: Task[];
}

export function Dashboard() {
  const navigate = useNavigate();
  const modals = useModals();
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showDebug, setShowDebug] = useState(false);
  const [debugMessages, setDebugMessages] = useState<Array<{
    id: number;
    message: string;
    timestamp: string;
  }>>([]);
  const messageIdCounter = useRef(0);
  const [formData, setFormData] = useState({
    location: '',
    src_ip: '',
    dst_ip: '',
    description: '',
    start_time: null as Date | null,
    end_time: null as Date | null,
    event_time: null as Date | null,
  });

  const addDebugMessage = (message: string) => {
    setDebugMessages(prev => {
      const updatedMessages = [...prev.slice(-99), {
        id: messageIdCounter.current++,
        timestamp: new Date().toISOString(),
        message
      }];
      return updatedMessages;
    });
  };

  const fetchJobs = async () => {
    try {
      const username = localStorage.getItem('username');
      if (!username) {
        throw new Error('User not logged in');
      }
      addDebugMessage('Fetching jobs for user: ' + username);
      const jobsResponse = await apiService.getJobs({ username });
      setJobs(jobsResponse);
      addDebugMessage(`Fetched ${jobsResponse.length} jobs`);
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to load jobs';
      setError(errorMessage);
      addDebugMessage('Error fetching jobs: ' + errorMessage);
      console.error('Error fetching jobs:', err);
    }
  };

  // Load user's jobs and available locations
  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Get available locations
        addDebugMessage('Fetching available locations');
        const locationsResponse = await apiService.getLocations();
        if (locationsResponse.locations) {
          setLocations(locationsResponse.locations.map(l => l.name));
          addDebugMessage(`Fetched ${locationsResponse.locations.length} locations`);
        } else {
          setError('No locations available');
          addDebugMessage('Error: No locations available in response');
        }

        // Get user's jobs
        await fetchJobs();
      } catch (err: any) {
        const errorMessage = err.message || 'Failed to load data';
        setError(errorMessage);
        addDebugMessage('Error loading data: ' + errorMessage);
        console.error('Error loading dashboard data:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      addDebugMessage('Submitting new job...');
      addDebugMessage(`Job data: ${JSON.stringify(formData)}`);

      await apiService.submitJob({
        location: formData.location,
        src_ip: formData.src_ip || undefined,
        dst_ip: formData.dst_ip || undefined,
        start_time: formData.start_time?.toISOString() || '',
        end_time: formData.end_time?.toISOString() || '',
        description: formData.description || '',
        event_time: formData.event_time?.toISOString(),
        tz: Intl.DateTimeFormat().resolvedOptions().timeZone
      });
      
      addDebugMessage('Job submitted successfully');
      
      // Clear form and refresh jobs
      setFormData({
        location: '',
        src_ip: '',
        dst_ip: '',
        description: '',
        start_time: null,
        end_time: null,
        event_time: null,
      });
      
      await fetchJobs();
    } catch (error: any) {
      const errorMessage = error.message || 'Job submission failed';
      setError(errorMessage);
      addDebugMessage('Error submitting job: ' + errorMessage);
      console.error('Job submission error:', error);
    }
  };

  const handleCancelJob = async (jobId: number) => {
    try {
      await apiService.cancelJob(jobId);
      
      // Refresh jobs list
      const username = localStorage.getItem('username');
      if (!username) {
        throw new Error('User not logged in');
      }
      const jobsResponse = await apiService.getJobs();
      const userJobs = jobsResponse.filter(job => job.username === username);
      setJobs(userJobs);
    } catch (err: any) {
      setError(err.message || 'Failed to cancel job');
    }
  };

  const handleDeleteJob = async (jobId: number) => {
    modals.openConfirmModal({
      title: <Title order={3}>Delete Job</Title>,
      children: (
        <Text size="sm">
          Are you sure you want to delete this job? This action cannot be undone.
        </Text>
      ),
      labels: { confirm: 'Delete Job', cancel: 'Cancel' },
      confirmProps: { color: 'red' },
      onConfirm: async () => {
        try {
          await apiService.deleteJob(jobId);
          
          // Refresh jobs list
          const username = localStorage.getItem('username');
          if (!username) {
            throw new Error('User not logged in');
          }
          const jobsResponse = await apiService.getJobs();
          const userJobs = jobsResponse.filter(job => job.username === username);
          setJobs(userJobs);
        } catch (err: any) {
          setError(err.message || 'Failed to delete job');
        }
      },
    });
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
    };
    return colors[status] || 'gray';
  };

  const renderTasks = (job: Job) => {
    if (!job.tasks || job.tasks.length === 0) return null;
    
    return (
      <Table size="xs" mt="xs">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Sensor</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Started</Table.Th>
            <Table.Th>Completed</Table.Th>
            <Table.Th>Message</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {job.tasks.map(task => (
            <Table.Tr key={task.id}>
              <Table.Td>{task.sensor}</Table.Td>
              <Table.Td>
                <Badge color={getStatusColor(task.status)}>
                  {task.status}
                </Badge>
              </Table.Td>
              <Table.Td>{task.started ? new Date(task.started).toLocaleString() : '-'}</Table.Td>
              <Table.Td>{task.completed ? new Date(task.completed).toLocaleString() : '-'}</Table.Td>
              <Table.Td>{task.result_message || '-'}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    );
  };

  return (
    <Stack gap="lg">
      <Title order={2}>Dashboard</Title>

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )}

      {/* Job Creation Form */}
      <Paper shadow="sm" p="md" radius="md" withBorder>
        <form onSubmit={handleSubmit}>
          <Stack gap="md">
            <Title order={3}>Create New Job</Title>

            <Grid>
              <Grid.Col span={6}>
                <Select
                  label="Location"
                  placeholder={isLoading ? "Loading locations..." : "Select a location"}
                  data={locations}
                  value={formData.location}
                  onChange={(value) => setFormData(prev => ({ ...prev, location: value || '' }))}
                  required
                  disabled={isLoading || locations.length === 0}
                />
              </Grid.Col>
              <Grid.Col span={6}>
                <TextInput
                  label="Description"
                  placeholder="Job description"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                />
              </Grid.Col>
              <Grid.Col span={6}>
                <TextInput
                  label="Source IP"
                  placeholder="Enter source IP"
                  value={formData.src_ip}
                  onChange={(e) => setFormData(prev => ({ ...prev, src_ip: e.target.value }))}
                />
              </Grid.Col>
              <Grid.Col span={6}>
                <TextInput
                  label="Destination IP"
                  placeholder="Enter destination IP"
                  value={formData.dst_ip}
                  onChange={(e) => setFormData(prev => ({ ...prev, dst_ip: e.target.value }))}
                />
              </Grid.Col>
              <Grid.Col span={6}>
                <DateTimePicker
                  label="Event Time (Optional)"
                  placeholder="Select event time"
                  value={formData.event_time}
                  onChange={(value) => setFormData(prev => ({ ...prev, event_time: value }))}
                />
              </Grid.Col>
              <Grid.Col span={6}>
                <Text size="sm" c="dimmed">
                  If event time is set, start and end times will be automatically calculated
                </Text>
              </Grid.Col>
              <Grid.Col span={6}>
                <DateTimePicker
                  label="Start Time"
                  value={formData.start_time}
                  onChange={(value) => setFormData(prev => ({ ...prev, start_time: value }))}
                  required={!formData.event_time}
                  disabled={!!formData.event_time}
                />
              </Grid.Col>
              <Grid.Col span={6}>
                <DateTimePicker
                  label="End Time"
                  value={formData.end_time}
                  onChange={(value) => setFormData(prev => ({ ...prev, end_time: value }))}
                  required={!formData.event_time}
                  disabled={!!formData.event_time}
                />
              </Grid.Col>
            </Grid>

            <Group justify="flex-end">
              <Button type="submit" loading={isLoading} disabled={locations.length === 0}>
                Submit Job
              </Button>
            </Group>
          </Stack>
        </form>
      </Paper>

      {/* Job History */}
      <Paper shadow="sm" p="md" radius="md" withBorder>
        <Title order={3} mb="md">Your Recent Jobs</Title>
        {isLoading ? (
          <Text>Loading jobs...</Text>
        ) : jobs.length === 0 ? (
          <Text c="dimmed">No jobs found</Text>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>ID</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Description</Table.Th>
                <Table.Th>Location</Table.Th>
                <Table.Th>IPs</Table.Th>
                <Table.Th>Time Range</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {jobs.map((job) => (
                <React.Fragment key={job.id}>
                  <Table.Tr>
                    <Table.Td>{job.id}</Table.Td>
                    <Table.Td>
                      <Badge color={getStatusColor(job.status)}>
                        {job.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {job.description}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {job.location}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {job.src_ip && job.dst_ip
                          ? `${job.src_ip} → ${job.dst_ip}`
                          : job.src_ip
                          ? `From: ${job.src_ip}`
                          : job.dst_ip
                          ? `To: ${job.dst_ip}`
                          : 'All'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {job.event_time ? (
                          <>Event: {new Date(job.event_time).toLocaleString()}</>
                        ) : (
                          <>
                            {new Date(job.start_time).toLocaleString()} -<br />
                            {new Date(job.end_time).toLocaleString()}
                          </>
                        )}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        {job.status === 'Running' && (
                          <ActionIcon
                            color="red"
                            onClick={() => handleCancelJob(job.id)}
                            title="Cancel Job"
                          >
                            <IconPlayerStop size={16} />
                          </ActionIcon>
                        )}
                        {['Complete', 'Failed', 'Cancelled'].includes(job.status) && (
                          <ActionIcon
                            color="red"
                            onClick={() => handleDeleteJob(job.id)}
                            title="Delete Job"
                          >
                            <IconTrash size={16} />
                          </ActionIcon>
                        )}
                        {job.result && (
                          <ActionIcon
                            color="blue"
                            onClick={() => navigate(`/analysis/${job.id}`)}
                            title="View Analysis"
                          >
                            <IconFileAnalytics size={16} />
                          </ActionIcon>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                  {renderTasks(job)}
                </React.Fragment>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      {/* Debug Messages Overlay */}
      {showDebug && (
        <Paper
          style={{
            position: 'fixed',
            bottom: 20,
            right: 20,
            zIndex: 1000,
            width: '400px',
            maxHeight: '300px',
            background: 'rgba(0, 0, 0, 0.8)',
            backdropFilter: 'blur(4px)',
          }}
        >
          <Stack gap="xs" p="xs">
            <Group justify="space-between">
              <Text size="xs" fw={500} c="dimmed">Debug Log ({debugMessages.length} messages)</Text>
              <Group gap="xs">
                <Text size="xs" c="dimmed">{new Date().toLocaleTimeString()}</Text>
                <ActionIcon 
                  size="xs" 
                  variant="subtle" 
                  color="gray" 
                  onClick={() => setShowDebug(false)}
                >
                  ×
                </ActionIcon>
              </Group>
            </Group>
            <ScrollArea h={250} scrollbarSize={8}>
              <Stack gap={4}>
                {debugMessages.map(msg => (
                  <Text 
                    key={msg.id} 
                    size="xs"
                    style={{ 
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      lineHeight: 1.2,
                      userSelect: 'text'
                    }}
                  >
                    <Text span c="dimmed" size="xs" style={{ userSelect: 'text' }}>
                      [{new Date(msg.timestamp).toLocaleTimeString()}]
                    </Text>{' '}
                    {msg.message}
                  </Text>
                ))}
              </Stack>
            </ScrollArea>
          </Stack>
        </Paper>
      )}

      {/* Debug Trigger Area */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          right: 0,
          width: '100px',
          height: '100px',
          zIndex: 999
        }}
        onMouseEnter={() => setShowDebug(true)}
      />
    </Stack>
  );
} 
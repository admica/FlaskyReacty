// PATH: src/components/dashboard/Dashboard.tsx

import { useState, useEffect } from 'react';
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
} from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { IconAlertCircle, IconTrash, IconPlayerStop, IconFileAnalytics } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useModals } from '@mantine/modals';
import apiService from '../../services/api';

interface Job {
  id: number;
  username: string;
  status: string;
  description: string;
  sensor: string;
  src_ip: string | null;
  dst_ip: string | null;
  start_time: string;
  end_time: string;
  event_time: string | null;
  started: string | null;
  completed: string | null;
  result: string | null;
  filename: string | null;
}

export function Dashboard() {
  const navigate = useNavigate();
  const modals = useModals();
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [sensors, setSensors] = useState<string[]>([]);
  const [formData, setFormData] = useState({
    sensor: '',
    src_ip: '',
    dst_ip: '',
    description: '',
    start_time: null as Date | null,
    end_time: null as Date | null,
  });

  const fetchJobs = async () => {
    try {
      const username = localStorage.getItem('username');
      if (!username) {
        throw new Error('User not logged in');
      }
      const jobsResponse = await apiService.getJobs();
      const userJobs = jobsResponse.filter(job => job.username === username);
      setJobs(userJobs);
    } catch (err: any) {
      setError(err.message || 'Failed to load jobs');
    }
  };

  // Load user's jobs and available sensors
  useEffect(() => {
    const loadData = async () => {
      try {
        // Get available sensors
        const sensorsResponse = await apiService.getSensors();
        setSensors(sensorsResponse.sensors.map((s: any) => s.name));

        // Get user's jobs
        await fetchJobs();
      } catch (err: any) {
        setError(err.message || 'Failed to load data');
      }
    };

    loadData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiService.submitJob({
        sensor: formData.sensor,
        src_ip: formData.src_ip || undefined,
        dst_ip: formData.dst_ip || undefined,
        start_time: formData.start_time?.toISOString() || '',
        end_time: formData.end_time?.toISOString() || '',
        description: formData.description || '',
      });
      // TODO: Add success notification
      fetchJobs();
    } catch (error) {
      console.error('Job submission failed:', error);
      // TODO: Add error notification
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

  return (
    <Stack gap="lg">
      <Title order={2}>Dashboard</Title>

      {/* Job Creation Form */}
      <Paper shadow="sm" p="md" radius="md" withBorder>
        <form onSubmit={handleSubmit}>
          <Stack gap="md">
            <Title order={3}>Create New Job</Title>

            {error && (
              <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
                {error}
              </Alert>
            )}

            <Grid>
              <Grid.Col span={6}>
                <Select
                  label="Sensor"
                  placeholder="Select a sensor"
                  data={sensors}
                  value={formData.sensor}
                  onChange={(value) => setFormData(prev => ({ ...prev, sensor: value || '' }))}
                  required
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
                  label="Start Time"
                  value={formData.start_time}
                  onChange={(value) => setFormData(prev => ({ ...prev, start_time: value }))}
                  required
                />
              </Grid.Col>
              <Grid.Col span={6}>
                <DateTimePicker
                  label="End Time"
                  value={formData.end_time}
                  onChange={(value) => setFormData(prev => ({ ...prev, end_time: value }))}
                  required
                />
              </Grid.Col>
            </Grid>

            <Group justify="flex-end">
              <Button type="submit">
                Submit Job
              </Button>
            </Group>
          </Stack>
        </form>
      </Paper>

      {/* Job History */}
      <Paper shadow="sm" p="md" radius="md" withBorder>
        <Title order={3} mb="md">Your Recent Jobs</Title>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Description</Table.Th>
              <Table.Th>Sensor</Table.Th>
              <Table.Th>IPs</Table.Th>
              <Table.Th>Time Range</Table.Th>
              <Table.Th>Result</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {jobs.map((job) => (
              <Table.Tr key={job.id}>
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {job.id}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Badge color={getStatusColor(job.status)}>
                    {job.status}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">
                    {job.description || '-'}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">
                    {job.sensor}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Stack gap={4}>
                    <Text size="sm" c="dimmed">
                      From: {job.src_ip || '-'}
                    </Text>
                    <Text size="sm" c="dimmed">
                      To: {job.dst_ip || '-'}
                    </Text>
                  </Stack>
                </Table.Td>
                <Table.Td>
                  <Stack gap={4}>
                    <Text size="sm">
                      Start: {new Date(job.start_time).toLocaleString()}
                    </Text>
                    <Text size="sm">
                      End: {new Date(job.end_time).toLocaleString()}
                    </Text>
                  </Stack>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">
                    {job.result || '-'}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <ActionIcon
                      variant="subtle"
                      color="blue"
                      onClick={() => navigate(`/jobs/${job.id}/analysis`)}
                      title="View Analysis"
                    >
                      <IconFileAnalytics size={16} />
                    </ActionIcon>
                    {(job.status === 'Running' || job.status === 'Submitted') && (
                      <ActionIcon
                        variant="subtle"
                        color="yellow"
                        onClick={() => handleCancelJob(job.id)}
                        title="Cancel Job"
                      >
                        <IconPlayerStop size={16} />
                      </ActionIcon>
                    )}
                    {(job.status === 'Complete' || job.status === 'Failed' || 
                      job.status === 'Cancelled' || job.status === 'Completed') && (
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        onClick={() => handleDeleteJob(job.id)}
                        title="Delete Job"
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>
    </Stack>
  );
} 
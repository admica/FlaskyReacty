// PATH: src/components/jobs/JobsPage.tsx

import { useState, useEffect } from 'react';
import {
  Box,
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
  ScrollArea,
  Modal,
  Grid,
  ActionIcon,
  Tooltip,
} from '@mantine/core';
import { useModals } from '@mantine/modals';
import {
  IconAlertCircle,
  IconRefresh,
  IconSearch,
  IconTrash,
  IconPlayerStop,
} from '@tabler/icons-react';
import apiService from '../../services/api';
import type { Job, Task } from '../../services/api';

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'Complete', label: 'Complete' },
  { value: 'Running', label: 'Running' },
  { value: 'Submitted', label: 'Submitted' },
  { value: 'Cancelled', label: 'Cancelled' },
  { value: 'Failed', label: 'Failed' },
  { value: 'Incomplete', label: 'Incomplete' },
  { value: 'Retrieving', label: 'Retrieving' },
  { value: 'Merging', label: 'Merging' },
];

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [locations, setLocations] = useState<string[]>([]);
  const [filters, setFilters] = useState({
    username: '',
    status: '',
    location: '',
    search: '',
  });

  const isAdmin = localStorage.getItem('isAdmin') === 'true';
  const modals = useModals();

  const loadJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getJobs();
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
        .map((sensor) => sensor.location)
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

  const handleCancelJob = async (jobId: number) => {
    modals.openConfirmModal({
      title: <Title order={3}>Cancel Job</Title>,
      children: (
        <Text size="sm">
          Are you sure you want to cancel this job? This will stop all running tasks.
        </Text>
      ),
      labels: { confirm: 'Cancel Job', cancel: 'Keep Running' },
      confirmProps: { color: 'red' },
      onConfirm: async () => {
        try {
          await apiService.cancelJob(jobId);
          await loadJobs();
        } catch (err: any) {
          setError(err.message || 'Failed to cancel job');
        }
      },
    });
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
          await loadJobs();
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

  // Filter jobs based on search criteria
  const filteredJobs = jobs.filter(job => {
    const searchLower = filters.search.toLowerCase();
    const matchesSearch = !filters.search || 
      job.description?.toLowerCase().includes(searchLower) ||
      job.src_ip?.toLowerCase().includes(searchLower) ||
      job.dst_ip?.toLowerCase().includes(searchLower);

    return (
      matchesSearch &&
      (!filters.username || job.submitted_by.toLowerCase().includes(filters.username.toLowerCase())) &&
      (!filters.status || job.status === filters.status) &&
      (!filters.location || job.location === filters.location)
    );
  });

  // Calculate job statistics
  const jobStats = {
    total: filteredJobs.length,
    running: filteredJobs.filter(job => job.status === 'Running').length,
    completed: filteredJobs.filter(job => job.status === 'Complete').length,
    failed: filteredJobs.filter(job => job.status === 'Failed').length,
  };

  return (
    <Box p="md">
      <Stack gap="md">
        <Group justify="space-between" align="center">
          <Title order={2}>Jobs</Title>
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

        {/* Job Statistics */}
        <Paper withBorder p="md">
          <Title order={3} mb="md">Job Statistics</Title>
          <Grid>
            <Grid.Col span={3}>
              <Paper withBorder p="xs">
                <Text size="sm" c="dimmed">Total Jobs</Text>
                <Text fw={700} size="xl">{jobStats.total}</Text>
              </Paper>
            </Grid.Col>
            <Grid.Col span={3}>
              <Paper withBorder p="xs">
                <Text size="sm" c="dimmed">Running</Text>
                <Text fw={700} size="xl" c="blue">{jobStats.running}</Text>
              </Paper>
            </Grid.Col>
            <Grid.Col span={3}>
              <Paper withBorder p="xs">
                <Text size="sm" c="dimmed">Completed</Text>
                <Text fw={700} size="xl" c="green">{jobStats.completed}</Text>
              </Paper>
            </Grid.Col>
            <Grid.Col span={3}>
              <Paper withBorder p="xs">
                <Text size="sm" c="dimmed">Failed</Text>
                <Text fw={700} size="xl" c="red">{jobStats.failed}</Text>
              </Paper>
            </Grid.Col>
          </Grid>
        </Paper>

        {/* Filters */}
        <Paper withBorder p="md">
          <Grid>
            <Grid.Col span={3}>
              <TextInput
                placeholder="Filter by username"
                value={filters.username}
                onChange={(e) => setFilters(prev => ({ ...prev, username: e.target.value }))}
                leftSection={<IconSearch size={16} />}
              />
            </Grid.Col>
            <Grid.Col span={3}>
              <Select
                placeholder="Filter by status"
                data={STATUS_OPTIONS}
                value={filters.status}
                onChange={(value) => setFilters(prev => ({ ...prev, status: value || '' }))}
                clearable
              />
            </Grid.Col>
            <Grid.Col span={3}>
              <Select
                placeholder="Filter by location"
                data={locations.map(loc => ({ value: loc, label: loc }))}
                value={filters.location}
                onChange={(value) => setFilters(prev => ({ ...prev, location: value || '' }))}
                clearable
              />
            </Grid.Col>
            <Grid.Col span={3}>
              <TextInput
                placeholder="Search description or IP"
                value={filters.search}
                onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                leftSection={<IconSearch size={16} />}
              />
            </Grid.Col>
          </Grid>
        </Paper>

        {/* Jobs List */}
        <Paper pos="relative" p="md" withBorder>
          <LoadingOverlay visible={loading} />
          
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
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filteredJobs.map((job) => (
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
                    <Table.Td onClick={(e) => e.stopPropagation()}>
                      <Group gap="xs">
                        {isAdmin && job.status === 'Running' && (
                          <Tooltip label="Cancel Job">
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              onClick={() => handleCancelJob(job.id)}
                            >
                              <IconPlayerStop size={16} />
                            </ActionIcon>
                          </Tooltip>
                        )}
                        {isAdmin && (
                          <Tooltip label="Delete Job">
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              onClick={() => handleDeleteJob(job.id)}
                            >
                              <IconTrash size={16} />
                            </ActionIcon>
                          </Tooltip>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Paper>

        {/* Job Details Modal */}
        <Modal
          opened={!!selectedJob}
          onClose={() => setSelectedJob(null)}
          title={<Title order={3}>Job {selectedJob?.id} Details</Title>}
          size="90%"
          styles={{
            body: {
              minWidth: '1000px'
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
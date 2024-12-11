// PATH: src/components/jobs/JobsPage.tsx

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Table,
    Group,
    Text,
    Badge,
    ActionIcon,
    Paper,
    Title,
    LoadingOverlay,
    Alert,
    Pagination,
    TextInput,
    Select,
    Grid,
    Button,
    Tooltip,
    Box,
    Modal,
    Stack,
} from '@mantine/core';
import { useModals } from '@mantine/modals';
import {
    IconAlertCircle,
    IconPlayerPlay,
    IconTrash,
    IconPlayerStop,
    IconSearch,
    IconRefresh,
    IconFileAnalytics,
} from '@tabler/icons-react';
import apiService, { Job } from '../../services/api';

const ITEMS_PER_PAGE = 50;

const STATUS_OPTIONS = [
    { value: '', label: 'All Statuses' },
    { value: 'Complete', label: 'Complete' },
    { value: 'Running', label: 'Running' },
    { value: 'Submitted', label: 'Submitted' },
    { value: 'Cancelled', label: 'Cancelled' },
    { value: 'Failed', label: 'Failed' },
    { value: 'Incomplete', label: 'Incomplete' },
];

export function JobsPage() {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [currentPage, setCurrentPage] = useState(1);
    const [selectedJob, setSelectedJob] = useState<Job | null>(null);
    const navigate = useNavigate();
    const modals = useModals();
    const isAdmin = localStorage.getItem('isAdmin') === 'true';
    const currentUser = localStorage.getItem('username');

    // Filter states
    const [filters, setFilters] = useState({
        username: '',
        status: '',
        sensor: '',
        description: '',
    });

    const canModifyJob = (job: Job) => {
        return isAdmin || job.username === currentUser;
    };

    const loadJobs = async () => {
        try {
            setLoading(true);
            const data = await apiService.getJobs();
            setJobs(data);
            setError(null);
        } catch (err: any) {
            setError(err.error || 'Failed to load jobs');
            console.error('Error loading jobs:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadJobs();
        // Poll for updates every 30 seconds
        const interval = setInterval(loadJobs, 30000);
        return () => clearInterval(interval);
    }, []);

    const handleCancelJob = async (jobId: number) => {
        try {
            await apiService.cancelJob(jobId);
            await loadJobs();
        } catch (err: any) {
            setError(err.error || 'Failed to cancel job');
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
                    await loadJobs();
                } catch (err: any) {
                    setError(err.error || 'Failed to delete job');
                }
            },
        });
    };

    const handleRunSimilar = (job: Job) => {
        navigate('/dashboard', { state: { jobTemplate: job } });
    };

    const handleViewAnalysis = (jobId: number) => {
        navigate(`/jobs/${jobId}/analysis`);
    };

    const getStatusColor = (status: string) => {
        const colors: Record<string, string> = {
            'Complete': 'green',
            'Running': 'blue',
            'Submitted': 'yellow',
            'Cancelled': 'gray',
            'Failed': 'red',
            'Incomplete': 'red',
        };
        return colors[status] || 'gray';
    };

    // Filter jobs based on current filters
    const filteredJobs = jobs.filter(job => {
        return (
            (!filters.username || job.username.toLowerCase().includes(filters.username.toLowerCase())) &&
            (!filters.status || job.status === filters.status) &&
            (!filters.sensor || job.sensor.toLowerCase().includes(filters.sensor.toLowerCase())) &&
            (!filters.description || job.description.toLowerCase().includes(filters.description.toLowerCase()))
        );
    });

    // Calculate pagination
    const totalPages = Math.ceil(filteredJobs.length / ITEMS_PER_PAGE);
    const paginatedJobs = filteredJobs.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    const formatBytes = (bytes: string) => {
        if (!bytes) return '-';
        return bytes.replace(/(\d+)([KMGT]?B)/, (_, num, unit) => {
            return `${Number(num).toLocaleString()} ${unit}`;
        });
    };

    const handleJobClick = (job: Job) => {
        setSelectedJob(job);
    };

    return (
        <div style={{ position: 'relative' }}>
            <LoadingOverlay visible={loading} />
            
            <Group justify="space-between" mb="md">
                <Title order={2}>Jobs</Title>
                <Button
                    leftSection={<IconRefresh size={16} />}
                    variant="light"
                    onClick={loadJobs}
                >
                    Refresh
                </Button>
            </Group>

            {error && (
                <Alert 
                    icon={<IconAlertCircle size={16} />}
                    color="red"
                    mb="md"
                    title="Error"
                    variant="light"
                >
                    {error}
                </Alert>
            )}

            {/* Filters */}
            <Paper withBorder p="md" mb="md">
                <Grid>
                    <Grid.Col span={3}>
                        <TextInput
                            placeholder="Filter by username"
                            value={filters.username}
                            onChange={(e) => setFilters(f => ({ ...f, username: e.target.value }))}
                            leftSection={<IconSearch size={16} />}
                        />
                    </Grid.Col>
                    <Grid.Col span={3}>
                        <Select
                            placeholder="Filter by status"
                            value={filters.status}
                            onChange={(value) => setFilters(f => ({ ...f, status: value || '' }))}
                            data={STATUS_OPTIONS}
                            clearable
                        />
                    </Grid.Col>
                    <Grid.Col span={3}>
                        <TextInput
                            placeholder="Filter by sensor"
                            value={filters.sensor}
                            onChange={(e) => setFilters(f => ({ ...f, sensor: e.target.value }))}
                            leftSection={<IconSearch size={16} />}
                        />
                    </Grid.Col>
                    <Grid.Col span={3}>
                        <TextInput
                            placeholder="Filter by description"
                            value={filters.description}
                            onChange={(e) => setFilters(f => ({ ...f, description: e.target.value }))}
                            leftSection={<IconSearch size={16} />}
                        />
                    </Grid.Col>
                </Grid>
            </Paper>

            <Paper withBorder>
                <Box style={{ overflowX: 'auto' }}>
                    <Table striped highlightOnHover>
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>ID</Table.Th>
                                <Table.Th>Status</Table.Th>
                                <Table.Th>Description</Table.Th>
                                <Table.Th>Time Range</Table.Th>
                                <Table.Th>Source IP</Table.Th>
                                <Table.Th>Dest IP</Table.Th>
                                <Table.Th>Sensor</Table.Th>
                                <Table.Th>Result</Table.Th>
                                <Table.Th>Actions</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {paginatedJobs.map((job) => (
                                <Table.Tr 
                                    key={job.id}
                                    style={{ cursor: 'pointer' }}
                                    onClick={() => handleJobClick(job)}
                                >
                                    <Table.Td>{job.id}</Table.Td>
                                    <Table.Td>
                                        <Badge color={getStatusColor(job.status)}>
                                            {job.status}
                                        </Badge>
                                    </Table.Td>
                                    <Table.Td>
                                        <Text lineClamp={1}>{job.description}</Text>
                                    </Table.Td>
                                    <Table.Td>
                                        <Stack gap={1}>
                                            <Text size="sm">Start: {job.start_time ? new Date(job.start_time).toLocaleString() : '-'}</Text>
                                            <Text size="sm">End: {job.end_time ? new Date(job.end_time).toLocaleString() : '-'}</Text>
                                        </Stack>
                                    </Table.Td>
                                    <Table.Td>
                                        <Text ff="monospace">{job.src_ip || '-'}</Text>
                                    </Table.Td>
                                    <Table.Td>
                                        <Text ff="monospace">{job.dst_ip || '-'}</Text>
                                    </Table.Td>
                                    <Table.Td>{job.sensor}</Table.Td>
                                    <Table.Td>
                                        <Text size="sm">{formatBytes(job.result || '-')}</Text>
                                    </Table.Td>
                                    <Table.Td onClick={(e) => e.stopPropagation()}>
                                        <Group gap="xs">
                                            {/* Anyone can run similar */}
                                            <Tooltip label="Run Similar">
                                                <ActionIcon
                                                    variant="subtle"
                                                    color="blue"
                                                    onClick={() => handleRunSimilar(job)}
                                                >
                                                    <IconPlayerPlay size={16} />
                                                </ActionIcon>
                                            </Tooltip>

                                            {/* Anyone can view analysis if complete */}
                                            {job.status === 'Complete' && (
                                                <Tooltip label="View Analysis">
                                                    <ActionIcon
                                                        variant="subtle"
                                                        color="blue"
                                                        onClick={() => handleViewAnalysis(job.id)}
                                                    >
                                                        <IconFileAnalytics size={16} />
                                                    </ActionIcon>
                                                </Tooltip>
                                            )}

                                            {/* Owner or admin can cancel if Running/Submitted */}
                                            {canModifyJob(job) && (job.status === 'Running' || job.status === 'Submitted') && (
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

                                            {/* Owner or admin can delete if Complete/Cancelled/Failed/Incomplete */}
                                            {canModifyJob(job) && ['Complete', 'Cancelled', 'Failed', 'Incomplete'].includes(job.status) && (
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
                </Box>

                {totalPages > 1 && (
                    <Group justify="center" mt="md" mb="sm">
                        <Pagination
                            value={currentPage}
                            onChange={setCurrentPage}
                            total={totalPages}
                        />
                    </Group>
                )}
            </Paper>

            {/* Job Details Modal */}
            <Modal
                opened={!!selectedJob}
                onClose={() => setSelectedJob(null)}
                title={<Title order={3}>Job Details</Title>}
                size="lg"
            >
                {selectedJob && (
                    <Grid>
                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">ID:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.id}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Status:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Badge color={getStatusColor(selectedJob.status)}>
                                {selectedJob.status}
                            </Badge>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Description:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.description}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Start Time:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.start_time ? new Date(selectedJob.start_time).toLocaleString() : '-'}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">End Time:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.end_time ? new Date(selectedJob.end_time).toLocaleString() : '-'}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Event Time:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.event_time ? new Date(selectedJob.event_time).toLocaleString() : '-'}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Source IP:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text ff="monospace">{selectedJob.src_ip || '-'}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Destination IP:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text ff="monospace">{selectedJob.dst_ip || '-'}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Sensor:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.sensor}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Result:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{formatBytes(selectedJob.result || '-')}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Started:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.started ? new Date(selectedJob.started).toLocaleString() : '-'}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Completed:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.completed ? new Date(selectedJob.completed).toLocaleString() : '-'}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Filename:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.filename || '-'}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Timezone:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.tz || '-'}</Text>
                        </Grid.Col>

                        <Grid.Col span={8}>
                            <Text fw={500} ta="right">Owner:</Text>
                        </Grid.Col>
                        <Grid.Col span={16}>
                            <Text>{selectedJob.username}</Text>
                        </Grid.Col>
                    </Grid>
                )}
            </Modal>
        </div>
    );
} 
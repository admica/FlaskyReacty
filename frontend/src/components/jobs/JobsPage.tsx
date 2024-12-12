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
    Collapse,
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
    IconChevronDown,
    IconChevronRight,
} from '@tabler/icons-react';
import apiService, { Job, Task } from '../../services/api';

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
    const [expandedJobIds, setExpandedJobIds] = useState<number[]>([]);
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
        // Track if the component is mounted
        let mounted = true;

        const fetchJobs = async () => {
            if (!mounted) return;
            await loadJobs();
        };

        // Initial load
        fetchJobs();

        // Set up polling interval
        const interval = setInterval(fetchJobs, 30000);

        // Cleanup function
        return () => {
            mounted = false;
            clearInterval(interval);
        };
    }, []);

    const handleCancelJob = async (jobId: number) => {
        try {
            await apiService.cancelJob(jobId);
            await loadJobs();
        } catch (err: any) {
            setError(err.error || 'Failed to cancel job');
        }
    };

    const handleCancelTask = async (jobId: number, sensor: string) => {
        try {
            await apiService.cancelTask(jobId, sensor);
            await loadJobs();
        } catch (err: any) {
            setError(err.error || 'Failed to cancel task');
        }
    };

    const handleDeleteJob = async (jobId: number) => {
        modals.openConfirmModal({
            title: <Title order={3}>Delete Job</Title>,
            children: (
                <Text size="sm">
                    Are you sure you want to delete this job and all its tasks? This action cannot be undone.
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

    const handleDeleteTask = async (jobId: number, sensor: string) => {
        modals.openConfirmModal({
            title: <Title order={3}>Delete Task</Title>,
            children: (
                <Text size="sm">
                    Are you sure you want to delete this task? This action cannot be undone.
                </Text>
            ),
            labels: { confirm: 'Delete Task', cancel: 'Cancel' },
            confirmProps: { color: 'red' },
            onConfirm: async () => {
                try {
                    await apiService.deleteTask(jobId, sensor);
                    await loadJobs();
                } catch (err: any) {
                    setError(err.error || 'Failed to delete task');
                }
            },
        });
    };

    const handleRunSimilar = (job: Job) => {
        navigate('/dashboard', { state: { jobTemplate: job } });
    };

    const handleViewAnalysis = (jobId: number, sensor?: string) => {
        const path = sensor ? 
            `/jobs/${jobId}/tasks/${sensor}/analysis` :
            `/jobs/${jobId}/analysis`;
        navigate(path);
    };

    const getStatusColor = (status: string) => {
        const colors: Record<string, string> = {
            'Complete': 'green',
            'Running': 'blue',
            'Submitted': 'yellow',
            'Cancelled': 'gray',
            'Failed': 'red',
            'Incomplete': 'red',
            'Retrieving': 'cyan',
        };
        return colors[status] || 'gray';
    };

    const toggleJobExpanded = (jobId: number) => {
        setExpandedJobIds(prev => 
            prev.includes(jobId) 
                ? prev.filter(id => id !== jobId)
                : [...prev, jobId]
        );
    };

    // Filter jobs based on current filters
    const filteredJobs = jobs.filter(job => {
        return (
            (!filters.username || job.username.toLowerCase().includes(filters.username.toLowerCase())) &&
            (!filters.status || job.status === filters.status) &&
            (!filters.sensor || job.tasks.some(task => task.sensor.toLowerCase().includes(filters.sensor.toLowerCase()))) &&
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

    const renderTaskRow = (task: Task, jobId: number) => (
        <Table.Tr key={`${jobId}-${task.sensor}`} style={{ backgroundColor: 'rgba(0,0,0,0.03)' }}>
            <Table.Td colSpan={2} pl={40}>
                <Group>
                    <Text>Sensor: {task.sensor}</Text>
                    <Badge color={getStatusColor(task.status)}>{task.status}</Badge>
                </Group>
            </Table.Td>
            <Table.Td>{task.result || '-'}</Table.Td>
            <Table.Td colSpan={2}>{task.filename || '-'}</Table.Td>
            <Table.Td>{task.completed || '-'}</Table.Td>
            <Table.Td>{task.analysis || '-'}</Table.Td>
            <Table.Td>
                <Group>
                    {task.status === 'Running' && (
                        <Tooltip label="Cancel Task">
                            <ActionIcon 
                                color="red" 
                                onClick={() => handleCancelTask(jobId, task.sensor)}
                                disabled={!canModifyJob(job)}
                            >
                                <IconPlayerStop size={16} />
                            </ActionIcon>
                        </Tooltip>
                    )}
                    {task.status === 'Complete' && task.analysis && (
                        <Tooltip label="View Analysis">
                            <ActionIcon 
                                color="blue" 
                                onClick={() => handleViewAnalysis(jobId, task.sensor)}
                            >
                                <IconFileAnalytics size={16} />
                            </ActionIcon>
                        </Tooltip>
                    )}
                    <Tooltip label="Delete Task">
                        <ActionIcon 
                            color="red" 
                            onClick={() => handleDeleteTask(jobId, task.sensor)}
                            disabled={!canModifyJob(job)}
                        >
                            <IconTrash size={16} />
                        </ActionIcon>
                    </Tooltip>
                </Group>
            </Table.Td>
        </Table.Tr>
    );

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
                                <Table.Th></Table.Th>
                                <Table.Th>ID</Table.Th>
                                <Table.Th>Status</Table.Th>
                                <Table.Th>Description</Table.Th>
                                <Table.Th>Time Range</Table.Th>
                                <Table.Th>Source IP</Table.Th>
                                <Table.Th>Dest IP</Table.Th>
                                <Table.Th>Actions</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {paginatedJobs.map((job) => (
                                <>
                                    <Table.Tr key={job.id}>
                                        <Table.Td>
                                            <ActionIcon
                                                onClick={() => toggleJobExpanded(job.id)}
                                                variant="subtle"
                                            >
                                                {expandedJobIds.includes(job.id) ? 
                                                    <IconChevronDown size={16} /> : 
                                                    <IconChevronRight size={16} />
                                                }
                                            </ActionIcon>
                                        </Table.Td>
                                        <Table.Td>{job.id}</Table.Td>
                                        <Table.Td>
                                            <Badge color={getStatusColor(job.status)}>
                                                {job.status}
                                            </Badge>
                                        </Table.Td>
                                        <Table.Td>{job.description}</Table.Td>
                                        <Table.Td>
                                            {new Date(job.start_time).toLocaleString()} -<br/>
                                            {new Date(job.end_time).toLocaleString()}
                                        </Table.Td>
                                        <Table.Td>{job.src_ip}</Table.Td>
                                        <Table.Td>{job.dst_ip}</Table.Td>
                                        <Table.Td>
                                            <Group>
                                                {job.status === 'Running' && (
                                                    <Tooltip label="Cancel Job">
                                                        <ActionIcon 
                                                            color="red" 
                                                            onClick={() => handleCancelJob(job.id)}
                                                            disabled={!canModifyJob(job)}
                                                        >
                                                            <IconPlayerStop size={16} />
                                                        </ActionIcon>
                                                    </Tooltip>
                                                )}
                                                <Tooltip label="Run Similar Job">
                                                    <ActionIcon 
                                                        color="blue" 
                                                        onClick={() => handleRunSimilar(job)}
                                                    >
                                                        <IconPlayerPlay size={16} />
                                                    </ActionIcon>
                                                </Tooltip>
                                                {job.status === 'Complete' && (
                                                    <Tooltip label="View Combined Analysis">
                                                        <ActionIcon 
                                                            color="blue" 
                                                            onClick={() => handleViewAnalysis(job.id)}
                                                        >
                                                            <IconFileAnalytics size={16} />
                                                        </ActionIcon>
                                                    </Tooltip>
                                                )}
                                                <Tooltip label="Delete Job">
                                                    <ActionIcon 
                                                        color="red" 
                                                        onClick={() => handleDeleteJob(job.id)}
                                                        disabled={!canModifyJob(job)}
                                                    >
                                                        <IconTrash size={16} />
                                                    </ActionIcon>
                                                </Tooltip>
                                            </Group>
                                        </Table.Td>
                                    </Table.Tr>
                                    {expandedJobIds.includes(job.id) && job.tasks.map(task => 
                                        renderTaskRow(task, job.id)
                                    )}
                                </>
                            ))}
                        </Table.Tbody>
                    </Table>
                </Box>

                {totalPages > 1 && (
                    <Group justify="center" mt="md">
                        <Pagination
                            total={totalPages}
                            value={currentPage}
                            onChange={setCurrentPage}
                        />
                    </Group>
                )}
            </Paper>
        </div>
    );
} 
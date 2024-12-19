// PATH: src/components/jobs/JobsPage.tsx

import { useState, useEffect, useRef } from 'react';
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
    ScrollArea,
    HoverCard,
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

interface DebugMessage {
    id: number;
    message: string;
    timestamp: string;
}

export function JobsPage() {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentPage, setCurrentPage] = useState(1);
    const [expandedJobIds, setExpandedJobIds] = useState<number[]>([]);
    const [filters, setFilters] = useState({
        username: '',
        status: '',
        sensor: '',
        description: ''
    });

    // Debug log state
    const [showDebug, setShowDebug] = useState(false);
    const [debugMessages, setDebugMessages] = useState<DebugMessage[]>([]);
    const messageIdCounter = useRef(0);
    const scrollRef = useRef<HTMLDivElement>(null);

    const navigate = useNavigate();
    const modals = useModals();

    const addDebugMessage = (message: string) => {
        setDebugMessages(prev => {
            const updatedMessages = [...prev.slice(-99), {
                id: messageIdCounter.current++,
                timestamp: new Date().toLocaleTimeString(),
                message
            }];
            // Auto-scroll to bottom
            setTimeout(() => {
                if (scrollRef.current) {
                    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
                }
            }, 100);
            return updatedMessages;
        });
    };

    useEffect(() => {
        (window as any).addDebugMessage = addDebugMessage;
        return () => {
            delete (window as any).addDebugMessage;
        };
    }, []);

    const loadJobs = async () => {
        setLoading(true);
        setError(null);
        try {
            addDebugMessage('Fetching jobs...');
            const data = await apiService.getJobs();
            addDebugMessage(`API Response: ${JSON.stringify(data)}`);
            if (!data) {
                throw new Error('No data returned from API');
            }
            setJobs(data);
            addDebugMessage(`Successfully fetched ${data.length} jobs`);
        } catch (err: any) {
            const errorMessage = err.message || 'Failed to load jobs';
            console.error('Job loading error:', err);
            setError(errorMessage);
            addDebugMessage(`Error loading jobs: ${errorMessage}`);
            if (err.response) {
                addDebugMessage(`Response status: ${err.response.status}`);
                addDebugMessage(`Response data: ${JSON.stringify(err.response.data)}`);
                addDebugMessage(`Request URL: ${err.response.config?.url}`);
                addDebugMessage(`Request method: ${err.response.config?.method}`);
                addDebugMessage(`Request headers: ${JSON.stringify(err.response.config?.headers)}`);
            } else if (err.request) {
                addDebugMessage('No response received from server');
                addDebugMessage(`Request URL: ${err.request.url}`);
                addDebugMessage(`Request method: ${err.request.method}`);
            } else {
                addDebugMessage('Error setting up request');
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadJobs();
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

    const handleCancelTask = async (jobId: number, sensor: string) => {
        modals.openConfirmModal({
            title: <Title order={3}>Cancel Task</Title>,
            children: (
                <Text size="sm">
                    Are you sure you want to cancel this task?
                </Text>
            ),
            labels: { confirm: 'Cancel Task', cancel: 'Keep Running' },
            confirmProps: { color: 'red' },
            onConfirm: async () => {
                try {
                    await apiService.cancelTask(jobId, sensor);
                    await loadJobs();
                } catch (err: any) {
                    setError(err.message || 'Failed to cancel task');
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
                    setError(err.message || 'Failed to delete task');
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
            'Merging': 'violet'
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

    // Add filtering and sorting options
    const handleFilterChange = (field: string, value: string) => {
        setFilters(prev => ({ ...prev, [field]: value }));
    };

    const filteredJobs = jobs.filter(job => {
        return (
            (!filters.username || job.submitted_by.toLowerCase().includes(filters.username.toLowerCase())) &&
            (!filters.status || job.status === filters.status) &&
            (!filters.sensor || job.tasks.some(task => task.sensor.toLowerCase().includes(filters.sensor.toLowerCase()))) &&
            (!filters.description || job.description.toLowerCase().includes(filters.description.toLowerCase()))
        );
    });

    // Implement pagination
    const paginatedJobs = filteredJobs.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);
    const totalPages = Math.ceil(filteredJobs.length / ITEMS_PER_PAGE);

    const renderTaskRow = (task: Task, jobId: number) => (
        <Table.Tr key={`${jobId}-${task.sensor}`} style={{ backgroundColor: 'rgba(0,0,0,0.03)' }}>
            <Table.Td colSpan={2} pl={40}>
                <Group>
                    <Text>Sensor: {task.sensor}</Text>
                    <Badge color={getStatusColor(task.status)}>{task.status}</Badge>
                </Group>
            </Table.Td>
            <Table.Td>{task.result_message || '-'}</Table.Td>
            <Table.Td>{task.pcap_size || '-'}</Table.Td>
            <Table.Td>{task.temp_path || '-'}</Table.Td>
            <Table.Td>
                {task.started_at && (
                    <Text size="sm">Started: {new Date(task.started_at).toLocaleString()}</Text>
                )}
                {task.completed_at && (
                    <Text size="sm">Completed: {new Date(task.completed_at).toLocaleString()}</Text>
                )}
            </Table.Td>
            <Table.Td>
                <Group>
                    {task.status === 'Running' && (
                        <Tooltip label="Cancel Task">
                            <ActionIcon 
                                color="red" 
                                onClick={() => handleCancelTask(jobId, task.sensor)}
                            >
                                <IconPlayerStop size={16} />
                            </ActionIcon>
                        </Tooltip>
                    )}
                    {task.status === 'Complete' && (
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
                        >
                            <IconTrash size={16} />
                        </ActionIcon>
                    </Tooltip>
                </Group>
            </Table.Td>
        </Table.Tr>
    );

    return (
        <Box pos="relative" pb={50}>
            <LoadingOverlay visible={loading} />
            
            {error && (
                <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red" mb="md">
                    {error}
                </Alert>
            )}

            <Paper p="md" mb="md">
                <Group position="apart" mb="md">
                    <Title order={2}>Jobs</Title>
                    <Button
                        onClick={loadJobs}
                        leftIcon={<IconRefresh size={16} />}
                        loading={loading}
                    >
                        Refresh
                    </Button>
                </Group>

                <Paper withBorder p="md" mb="md">
                    <Grid>
                        <Grid.Col span={6}>
                            <TextInput
                                placeholder="Filter by username"
                                value={filters.username}
                                onChange={(event) => handleFilterChange('username', event.currentTarget.value)}
                                icon={<IconSearch size={16} />}
                            />
                        </Grid.Col>
                        <Grid.Col span={6}>
                            <Select
                                placeholder="Filter by status"
                                data={STATUS_OPTIONS}
                                value={filters.status}
                                onChange={(value) => handleFilterChange('status', value || '')}
                            />
                        </Grid.Col>
                    </Grid>
                </Paper>

                <ScrollArea>
                    <Table striped highlightOnHover>
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>ID</Table.Th>
                                <Table.Th>Status</Table.Th>
                                <Table.Th>Description</Table.Th>
                                <Table.Th>Time Range</Table.Th>
                                <Table.Th>Source IP</Table.Th>
                                <Table.Th>Destination IP</Table.Th>
                                <Table.Th>Actions</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {paginatedJobs.map((job) => (
                                <React.Fragment key={job.id}>
                                    <Table.Tr>
                                        <Table.Td>{job.id}</Table.Td>
                                        <Table.Td>
                                            <Badge color={getStatusColor(job.status)}>{job.status}</Badge>
                                        </Table.Td>
                                        <Table.Td>{job.description}</Table.Td>
                                        <Table.Td>
                                            {job.start_time && job.end_time && (
                                                <>
                                                    {new Date(job.start_time).toLocaleString()} -<br/>
                                                    {new Date(job.end_time).toLocaleString()}
                                                </>
                                            )}
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
                                                <Tooltip label="Delete Job">
                                                    <ActionIcon
                                                        color="red"
                                                        onClick={() => handleDeleteJob(job.id)}
                                                    >
                                                        <IconTrash size={16} />
                                                    </ActionIcon>
                                                </Tooltip>
                                            </Group>
                                        </Table.Td>
                                    </Table.Tr>
                                    {expandedJobIds.includes(job.id) && (
                                        <>
                                            <Table.Tr style={{ backgroundColor: 'rgba(0,0,0,0.02)' }}>
                                                <Table.Td colSpan={2} />
                                                <Table.Td colSpan={6}>
                                                    <Text fw={500} mb="xs">Tasks</Text>
                                                </Table.Td>
                                            </Table.Tr>
                                            {job.tasks.map(task => renderTaskRow(task, job.id))}
                                        </>
                                    )}
                                </React.Fragment>
                            ))}
                        </Table.Tbody>
                    </Table>
                </ScrollArea>

                {totalPages > 1 && (
                    <Group position="center" mt="md">
                        <Pagination
                            total={totalPages}
                            value={currentPage}
                            onChange={setCurrentPage}
                        />
                    </Group>
                )}
            </Paper>

            <Box
                style={{
                    position: 'fixed',
                    bottom: 0,
                    right: 0,
                    width: '200px',
                    height: '100px',
                    display: 'flex',
                    alignItems: 'flex-end',
                    justifyContent: 'flex-end',
                    padding: '20px',
                    zIndex: 1000,
                }}
                onMouseEnter={() => setShowDebug(true)}
            >
                {showDebug ? (
                    <Paper
                        shadow="md"
                        style={{
                            position: 'absolute',
                            bottom: '20px',
                            right: '20px',
                            width: '400px',
                            background: 'rgba(0, 0, 0, 0.8)',
                            backdropFilter: 'blur(4px)',
                            border: 'none',
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
                                        c="dimmed"
                                        onClick={() => setShowDebug(false)}
                                    >
                                        ×
                                    </ActionIcon>
                                </Group>
                            </Group>
                            <ScrollArea h={250} scrollbarSize={8} viewportRef={scrollRef}>
                                <Stack gap={4}>
                                    {debugMessages.map(msg => (
                                        <Text key={msg.id} size="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
                                            [{msg.timestamp}] {msg.message}
                                        </Text>
                                    ))}
                                </Stack>
                            </ScrollArea>
                        </Stack>
                    </Paper>
                ) : (
                    <Box style={{ width: '100%', height: '100%' }} />
                )}
            </Box>
        </Box>
    );
} 
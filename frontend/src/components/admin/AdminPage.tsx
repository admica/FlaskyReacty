// PATH: src/components/admin/AdminPage.tsx
import { useEffect, useState, useRef } from 'react';
import { Container, Grid, Paper, Text, Title, RingProgress, Group, Stack, Table, Button, Card, ActionIcon, ScrollArea, Center, Box, Select, TextInput } from '@mantine/core';
import { IconDatabase, IconDeviceFloppy, IconCpu, IconRefresh, IconTrash, IconFileText } from '@tabler/icons-react';
import apiService from '../../services/api';
import { LogViewer } from './LogViewer';
import type { Admin } from '../../services/api';

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  
  if (days === 0) {
    return date.toLocaleTimeString();
  } else if (days === 1) {
    return 'Yesterday';
  } else if (days < 7) {
    return `${days} days ago`;
  } else {
    return date.toLocaleDateString();
  }
};

const formatDateTime = (date: string | null): string => {
  if (!date) return '-';
  return new Date(date).toLocaleString();
};

interface HealthStatus {
  status: string;
  components: {
    database: string;
    redis: string;
  };
  timestamp: string;
}

interface StorageInfo {
  path: string;
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
  percent_used: number;
  human_readable: {
    total: string;
    used: string;
    free: string;
  };
}

interface StorageStatus {
  storage: {
    [key: string]: StorageInfo;
  };
  timestamp: string;
}

interface DebugMessage {
  id: number;
  message: string;
  timestamp: string;
}

interface LogFile {
  name: string;
  size: number;
  modified: string;
}

export function AdminPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [storage, setStorage] = useState<StorageStatus | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isCacheOperationLoading, setIsCacheOperationLoading] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [logs, setLogs] = useState<LogFile[]>([]);
  const [selectedLog, setSelectedLog] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [debugMessages, setDebugMessages] = useState<DebugMessage[]>([]);
  const messageIdCounter = useRef(0);
  const isFetchingRef = useRef(false);
  const [refreshInterval, setRefreshInterval] = useState<string>('300');
  const [refreshProgress, setRefreshProgress] = useState(100);
  const [animatedProgress, setAnimatedProgress] = useState<{ [key: string]: number }>({});
  const [admins, setAdmins] = useState<Admin[]>([]);
  const username = localStorage.getItem('username');

  useEffect(() => {
    // Check if user is admin
    const isAdmin = localStorage.getItem('isAdmin') === 'true';
    if (!isAdmin) {
      console.log('Non-admin user attempting to access admin page');
      window.location.href = '/';
      return;
    }

    fetchAllData();
    loadAdmins();
  }, []);

  useEffect(() => {
    const interval = parseInt(refreshInterval);
    if (interval === 0) {
      setRefreshProgress(100);
      return;
    }

    // Update progress every 100ms
    const progressInterval = 100;
    const steps = interval * 1000 / progressInterval;
    const decrementAmount = 100 / steps;
    
    setRefreshProgress(100); // Reset progress when interval changes
    
    const progressTimer = setInterval(() => {
      setRefreshProgress(prev => Math.max(0, prev - decrementAmount));
    }, progressInterval);

    const refreshTimer = setInterval(() => {
      setRefreshProgress(100);
      fetchAllData();
    }, interval * 1000);

    return () => {
      clearInterval(progressTimer);
      clearInterval(refreshTimer);
    };
  }, [refreshInterval]);

  // Add animation effect when storage data changes
  useEffect(() => {
    if (storage) {
      // Reset all progress to 0
      const initialProgress: { [key: string]: number } = {};
      Object.keys(storage.storage).forEach(key => {
        initialProgress[key] = 0;
      });
      setAnimatedProgress(initialProgress);

      // Animate to actual values
      const duration = 1000; // 1 second animation
      const steps = 20; // Number of steps in animation
      const interval = duration / steps;

      let step = 0;
      const timer = setInterval(() => {
        step++;
        setAnimatedProgress(prev => {
          const newProgress: { [key: string]: number } = {};
          Object.entries(storage.storage).forEach(([key, info]) => {
            const target = info.percent_used;
            const current = prev[key] || 0;
            const increment = target / steps;
            newProgress[key] = Math.min(current + increment, target);
          });
          return newProgress;
        });

        if (step >= steps) {
          clearInterval(timer);
        }
      }, interval);

      return () => clearInterval(timer);
    }
  }, [storage]);

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

  const fetchAllData = async () => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    setIsRefreshing(true);
    addDebugMessage('Starting core data refresh');

    try {
      const [healthRes, storageRes, logsRes] = await Promise.all([
        apiService.getHealth(),
        apiService.getStorage(),
        apiService.getLogs()
      ]);

      if (healthRes) {
        setHealth(healthRes);
        addDebugMessage(`Health status: ${JSON.stringify(healthRes)}`);
      }
      if (storageRes) {
        setStorage(storageRes);
        addDebugMessage(`Storage info: ${JSON.stringify(storageRes)}`);
      }
      if (logsRes) {
        setLogs(logsRes.files);
        addDebugMessage(`Logs info: ${JSON.stringify(logsRes)}`);
      }
      addDebugMessage('Core data refresh complete');
    } catch (error: any) {
      console.error('Error fetching data:', error);
      addDebugMessage(`Error fetching data: ${error.message}`);
    } finally {
      setIsRefreshing(false);
      setIsLoading(false);
      isFetchingRef.current = false;
    }
  };

  const handleClearCache = async (cacheType: string) => {
    setIsCacheOperationLoading(cacheType + '-clear');
    try {
      addDebugMessage(`Clearing cache: ${cacheType}`);
      await apiService.clearCache(cacheType);
      await fetchAllData();
      addDebugMessage(`Cache cleared: ${cacheType}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addDebugMessage(`Error clearing cache: ${errorMessage}`);
      console.error('Error clearing cache:', error);
    } finally {
      setIsCacheOperationLoading(null);
    }
  };

  const handleRefreshCache = async (cacheType: string) => {
    setIsCacheOperationLoading(cacheType + '-refresh');
    try {
      addDebugMessage(`Refreshing cache: ${cacheType}`);
      await apiService.refreshCache(cacheType);
      await fetchAllData();
      addDebugMessage(`Cache refreshed: ${cacheType}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addDebugMessage(`Error refreshing cache: ${errorMessage}`);
      console.error('Error refreshing cache:', error);
    } finally {
      setIsCacheOperationLoading(null);
    }
  };

  const handleClearAllCaches = async () => {
    setIsCacheOperationLoading('all-clear');
    try {
      addDebugMessage('Clearing all caches...');
      await apiService.clearCache('all');
      await fetchAllData();
      addDebugMessage('All caches cleared');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addDebugMessage(`Error clearing all caches: ${errorMessage}`);
      console.error('Error clearing all caches:', error);
    } finally {
      setIsCacheOperationLoading(null);
    }
  };

  const handleRefreshAllCaches = async () => {
    setIsCacheOperationLoading('all-refresh');
    try {
      addDebugMessage('Refreshing all caches...');
      await Promise.all([
        apiService.refreshCache('sensors:admin'),
        apiService.refreshCache('sensors:user'),
        apiService.refreshCache('devices:*')
      ]);
      await fetchAllData();
      addDebugMessage('All caches refreshed');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addDebugMessage(`Error refreshing all caches: ${errorMessage}`);
      console.error('Error refreshing all caches:', error);
    } finally {
      setIsCacheOperationLoading(null);
    }
  };

  const getStatusColor = (status: string) => {
    return status === 'operational' || status === 'healthy' ? 'teal' : 'red';
  };

  const getStorageColor = (percent: number): string => {
    if (percent > 85) return 'red';
    if (percent > 70) return 'yellow';
    return 'blue';
  };

  const loadAdmins = async () => {
    try {
      addDebugMessage('Loading admin users...');
      const adminUsers = await apiService.getAdmins();
      setAdmins(adminUsers);
      addDebugMessage(`Loaded ${adminUsers.length} admin users`);
    } catch (error: any) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addDebugMessage(`Error loading admin users: ${errorMessage}`);
      console.error('Error loading admins:', error);
    }
  };

  if (isLoading) {
    return (
      <Container fluid style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Stack gap="md" align="center">
          <Text>Loading admin dashboard...</Text>
        </Stack>
      </Container>
    );
  }

  return (
    <Container fluid style={{ position: 'relative', minHeight: '100vh' }}>
      <Group justify="space-between" mb="md">
        <Title order={3}>System Administration</Title>
        <Group>
          <Box>
            <Text size="sm" mb={3}>Auto-refresh</Text>
            <Group gap="xs" align="center" style={{ height: 36 }}>
              <Select
                value={refreshInterval}
                onChange={(value) => setRefreshInterval(value || '300')}
                data={[
                  { value: '0', label: 'Manual refresh' },
                  { value: '10', label: '10 seconds' },
                  { value: '30', label: '30 seconds' },
                  { value: '180', label: '3 minutes' },
                  { value: '600', label: '10 minutes' },
                ]}
                styles={{ input: { height: 36 } }}
              />
              {refreshInterval !== '0' && (
                <Box 
                  style={{ 
                    width: 24, 
                    height: 24,
                    display: 'flex',
                    alignItems: 'center',
                    opacity: 0.8
                  }}
                >
                  <RingProgress
                    size={24}
                    thickness={3}
                    roundCaps
                    sections={[{ value: 100 - refreshProgress, color: 'blue' }]}
                  />
                </Box>
              )}
            </Group>
          </Box>
          <Button
            variant="light"
            loading={isRefreshing}
            onClick={fetchAllData}
            leftSection={<IconRefresh size={20} />}
          >
            Refresh
          </Button>
        </Group>
      </Group>

      <Grid>
        {/* System Health Section */}
        <Grid.Col span={3.3}>
          <Stack gap="md">
            <Paper shadow="sm" p="md" withBorder>
              <Group mb="md">
                <IconCpu size={24} />
                <Title order={3}>System Health</Title>
              </Group>
              
              {health ? (
                <Stack gap="md">
                  <Group justify="space-between">
                    <Text>Overall Status:</Text>
                    <Text fw={500} c={getStatusColor(health.status)}>
                      {health.status.toUpperCase()}
                    </Text>
                  </Group>
                  <Group justify="space-between">
                    <Text>Database:</Text>
                    <Text fw={500} c={getStatusColor(health.components.database)}>
                      {health.components.database.toUpperCase()}
                    </Text>
                  </Group>
                  <Group justify="space-between">
                    <Text>Redis Cache:</Text>
                    <Text fw={500} c={getStatusColor(health.components.redis)}>
                      {health.components.redis.toUpperCase()}
                    </Text>
                  </Group>
                  <Text size="xs" c="dimmed">
                    Last Updated: {new Date(health.timestamp).toLocaleString()}
                  </Text>
                </Stack>
              ) : (
                <Text c="dimmed">Loading health data...</Text>
              )}
            </Paper>
          </Stack>
        </Grid.Col>

        {/* Storage Status Section */}
        <Grid.Col span={8.7}>
          <Paper shadow="sm" p="md" withBorder>
            <Group mb="xs" justify="space-between">
              <Group gap="xs">
                <IconDatabase size={24} />
                <Title order={3}>Storage Status</Title>
              </Group>
              <Text size="sm" c="dimmed">
                Last Updated: {storage && new Date(storage.timestamp).toLocaleString()}
              </Text>
            </Group>

            {storage ? (
              <Grid>
                {Object.entries(storage.storage).map(([name, info]) => (
                  <Grid.Col span={4} key={name}>
                    <Card p="xs" withBorder>
                      <Group grow align="center">
                        {/* Left column - details */}
                        <Stack gap={2}>
                          <Text fw={500} size="sm">{name}</Text>
                          <Group gap="xs">
                            <Text size="xs">Used:</Text>
                            <Text size="xs" fw={500}>{info.human_readable.used}</Text>
                          </Group>
                          <Group gap="xs">
                            <Text size="xs">Free:</Text>
                            <Text size="xs" fw={500}>{info.human_readable.free}</Text>
                          </Group>
                          <Group gap="xs">
                            <Text size="xs">Total:</Text>
                            <Text size="xs" fw={500}>{info.human_readable.total}</Text>
                          </Group>
                          <Text size="xs" c="dimmed" mt={4} lineClamp={1}>
                            {info.path}
                          </Text>
                        </Stack>

                        {/* Right column - dial */}
                        <Center>
                          <RingProgress
                            size={112}
                            thickness={11}
                            roundCaps
                            sections={[{ 
                              value: animatedProgress[name] || 0, 
                              color: getStorageColor(info.percent_used) 
                            }]}
                            label={
                              <Text ta="center" fw={700} size="lg">
                                {Math.round(animatedProgress[name] || 0)}%
                              </Text>
                            }
                          />
                        </Center>
                      </Group>
                      {info.percent_used > 75 && (
                        <Text size="xs" c={info.percent_used > 85 ? 'red' : 'yellow'} mt="xs">
                          {info.percent_used > 90 ? 'Critical' : 'Warning'}: Low space
                        </Text>
                      )}
                    </Card>
                  </Grid.Col>
                ))}
              </Grid>
            ) : (
              <Text c="dimmed">Loading storage data...</Text>
            )}
          </Paper>
        </Grid.Col>

        {/* Logs Section */}
        <Grid.Col span={12}>
          <Paper p="md" withBorder>
            <Group justify="space-between" mb="xs">
              <Title order={3}>System Logs</Title>
              <Button
                variant="light"
                loading={isRefreshing}
                onClick={fetchAllData}
                leftSection={<IconRefresh size={20} />}
              >
                Refresh Logs
              </Button>
            </Group>

            <Grid>
              <Grid.Col span={3}>
                <ScrollArea h={400} scrollbarSize={8}>
                  <Stack gap={0}>
                    {logs.map((log) => (
                      <Group 
                        key={log.name} 
                        wrap="nowrap"
                        style={{ 
                          cursor: 'pointer',
                          backgroundColor: selectedLog === log.name ? 'var(--mantine-color-blue-light)' : 'transparent',
                          padding: '4px 8px',
                          borderRadius: '4px'
                        }}
                        onClick={() => setSelectedLog(log.name)}
                      >
                        <IconFileText size={14} style={{ flexShrink: 0 }} />
                        <Text size="sm" lineClamp={1} style={{ flex: 1 }}>{log.name}</Text>
                        <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
                          <Text size="xs" c="dimmed">{formatBytes(log.size)}</Text>
                          <Text size="xs" c="dimmed">•</Text>
                          <Text size="xs" c="dimmed" style={{ width: '70px' }}>{formatDate(log.modified)}</Text>
                        </Group>
                      </Group>
                    ))}
                  </Stack>
                </ScrollArea>
              </Grid.Col>
              <Grid.Col span={9}>
                {selectedLog ? (
                  <LogViewer 
                    logFile={selectedLog} 
                    onDebugMessage={addDebugMessage}
                  />
                ) : (
                  <Text c="dimmed">Select a log file to view its contents</Text>
                )}
              </Grid.Col>
            </Grid>
          </Paper>
        </Grid.Col>

        {/* Admin Users Section */}
        <Grid.Col span={12}>
          <Paper shadow="sm" p="md" withBorder>
            <Group mb="md" justify="space-between">
              <Title order={3}>Admin Users</Title>
            </Group>

            {/* Add Admin Form */}
            <Paper withBorder p="md" mb="md">
              <form onSubmit={(e) => {
                e.preventDefault();
                const form = e.currentTarget;
                const username = (form.elements.namedItem('username') as HTMLInputElement).value;
                if (username) {
                  addDebugMessage(`Adding new admin user: ${username}`);
                  apiService.addAdmin(username)
                    .then(() => {
                      addDebugMessage(`Successfully added admin user: ${username}`);
                      loadAdmins();
                      form.reset();
                    })
                    .catch(error => {
                      const errorMessage = error instanceof Error ? error.message : String(error);
                      addDebugMessage(`Error adding admin user: ${errorMessage}`);
                      console.error('Error adding admin:', error);
                    });
                }
              }}>
                <Group align="flex-end">
                  <TextInput
                    label="Username"
                    name="username"
                    placeholder="Enter username"
                    required
                    style={{ flex: 1 }}
                  />
                  <Button type="submit">Add Admin</Button>
                </Group>
              </form>
            </Paper>

            {/* Admin Users List */}
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Username</Table.Th>
                  <Table.Th>Added On</Table.Th>
                  <Table.Th>Last Active</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {admins.map((admin) => (
                  <Table.Tr key={admin.username}>
                    <Table.Td>{admin.username}</Table.Td>
                    <Table.Td>{formatDateTime(admin.created_at)}</Table.Td>
                    <Table.Td>{formatDateTime(admin.last_active)}</Table.Td>
                    <Table.Td>
                      <Button
                        variant="subtle"
                        color="red"
                        size="xs"
                        disabled={admin.username === username} // Prevent self-deletion
                        onClick={() => {
                          if (window.confirm(`Are you sure you want to remove admin privileges from ${admin.username}?`)) {
                            addDebugMessage(`Removing admin user: ${admin.username}`);
                            apiService.removeAdmin(admin.username)
                              .then(() => {
                                addDebugMessage(`Successfully removed admin user: ${admin.username}`);
                                loadAdmins();
                              })
                              .catch(error => {
                                const errorMessage = error instanceof Error ? error.message : String(error);
                                addDebugMessage(`Error removing admin user: ${errorMessage}`);
                                console.error('Error removing admin:', error);
                              });
                          }
                        }}
                      >
                        Remove Admin
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Paper>
        </Grid.Col>

        {/* Cache Status Section */}
        <Grid.Col span={12}>
          <Paper shadow="sm" p="md" withBorder>
            <Group mb="md" justify="space-between">
              <Group>
                <IconDeviceFloppy size={24} />
                <Title order={3}>Cache Status</Title>
              </Group>
              <Group>
                <Button 
                  variant="light"
                  color="red"
                  size="xs"
                  leftSection={<IconTrash size={14} />}
                  onClick={handleClearAllCaches}
                  loading={isCacheOperationLoading === 'all-clear'}
                >
                  Clear All Caches
                </Button>
                <Button 
                  variant="light"
                  color="blue"
                  size="xs"
                  leftSection={<IconRefresh size={14} />}
                  onClick={handleRefreshAllCaches}
                  loading={isCacheOperationLoading === 'all-refresh'}
                >
                  Refresh Caches
                </Button>
              </Group>
            </Group>
            
            <Table>
              <thead>
                <tr>
                  <th>Cache Type</th>
                  <th>Keys</th>
                  <th>Hit Ratio</th>
                  <th>Size</th>
                  <th>Last Updated</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Sensors (Admin)</td>
                  <td>sensors:admin</td>
                  <td>98.5%</td>
                  <td>245 KB</td>
                  <td>2 mins ago</td>
                  <td><Text c="teal">Active</Text></td>
                  <td>
                    <Group gap="xs">
                      <ActionIcon 
                        variant="subtle" 
                        color="blue" 
                        size="sm"
                        onClick={() => handleRefreshCache('sensors:admin')}
                        loading={isCacheOperationLoading === 'sensors:admin-refresh'}
                      >
                        <IconRefresh size={14} />
                      </ActionIcon>
                      <ActionIcon 
                        variant="subtle" 
                        color="red" 
                        size="sm"
                        onClick={() => handleClearCache('sensors:admin')}
                        loading={isCacheOperationLoading === 'sensors:admin-clear'}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Group>
                  </td>
                </tr>
                <tr>
                  <td>Sensors (User)</td>
                  <td>sensors:user</td>
                  <td>97.2%</td>
                  <td>180 KB</td>
                  <td>5 mins ago</td>
                  <td><Text c="teal">Active</Text></td>
                  <td>
                    <Group gap="xs">
                      <ActionIcon 
                        variant="subtle" 
                        color="blue" 
                        size="sm"
                        onClick={() => handleRefreshCache('sensors:user')}
                        loading={isCacheOperationLoading === 'sensors:user-refresh'}
                      >
                        <IconRefresh size={14} />
                      </ActionIcon>
                      <ActionIcon 
                        variant="subtle" 
                        color="red" 
                        size="sm"
                        onClick={() => handleClearCache('sensors:user')}
                        loading={isCacheOperationLoading === 'sensors:user-clear'}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Group>
                  </td>
                </tr>
                <tr>
                  <td>Device Cache</td>
                  <td>devices:*</td>
                  <td>95.8%</td>
                  <td>320 KB</td>
                  <td>12 mins ago</td>
                  <td><Text c="teal">Active</Text></td>
                  <td>
                    <Group gap="xs">
                      <ActionIcon 
                        variant="subtle" 
                        color="blue" 
                        size="sm"
                        onClick={() => handleRefreshCache('devices:*')}
                        loading={isCacheOperationLoading === 'devices:*-refresh'}
                      >
                        <IconRefresh size={14} />
                      </ActionIcon>
                      <ActionIcon 
                        variant="subtle" 
                        color="red" 
                        size="sm"
                        onClick={() => handleClearCache('devices:*')}
                        loading={isCacheOperationLoading === 'devices:*-clear'}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Group>
                  </td>
                </tr>
              </tbody>
            </Table>
          </Paper>
        </Grid.Col>
      </Grid>

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
                    <Text span c="dimmed" size="xs" style={{ userSelect: 'text' }}>[{msg.timestamp}]</Text>{' '}
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
    </Container>
  );
} 

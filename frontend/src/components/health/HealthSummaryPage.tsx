import { useState, useEffect, useRef } from 'react';
import { Box, Title, Text, Badge, Group, Stack, Card, Loader, Select, RingProgress, Tooltip, Paper, Grid, Table, Progress, ActionIcon, ScrollArea } from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import apiService from '../../services/api';
import type { HealthSummary } from '../../services/api';

// Add debug message interface
interface DebugMessage {
  id: number;
  message: string;
  timestamp: string;
}

export function HealthSummaryPage() {
  const [summaries, setSummaries] = useState<HealthSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshInterval, setRefreshInterval] = useState<string>('60');
  const [refreshProgress, setRefreshProgress] = useState(100);
  const [showDebug, setShowDebug] = useState(false);
  const [debugMessages, setDebugMessages] = useState<DebugMessage[]>([]);
  const messageIdCounter = useRef(0);

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

  const fetchSummaries = async () => {
    try {
      setLoading(true);
      addDebugMessage('Fetching health summaries...');
      const response = await apiService.getHealthSummary({});
      setSummaries(response.summaries || []);
      addDebugMessage(`Successfully fetched ${response.summaries?.length || 0} health summaries`);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching health summaries:', err);
      const errorMessage = err.message || 'Failed to fetch health summary data';
      setError(errorMessage);
      addDebugMessage(`Error fetching health summaries: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchSummaries();
  }, []);

  // Auto-refresh setup
  useEffect(() => {
    const interval = parseInt(refreshInterval);
    if (interval === 0) {
      setRefreshProgress(100);
      return;
    }

    const progressInterval = 100;
    const steps = interval * 1000 / progressInterval;
    const decrementAmount = 100 / steps;
    
    setRefreshProgress(100);
    
    const progressTimer = setInterval(() => {
      setRefreshProgress(prev => Math.max(0, prev - decrementAmount));
    }, progressInterval);

    const refreshTimer = setInterval(() => {
      setRefreshProgress(100);
      fetchSummaries();
    }, interval * 1000);

    return () => {
      clearInterval(progressTimer);
      clearInterval(refreshTimer);
    };
  }, [refreshInterval]);

  const getStatusColor = (status: 'online' | 'offline' | 'degraded') => {
    switch (status) {
      case 'online':
        return 'green';
      case 'offline':
        return 'red';
      case 'degraded':
        return 'yellow';
    }
  };

  if (loading && !summaries.length) {
    return (
      <Box p="md">
        <Group position="center">
          <Loader />
          <Text>Loading health summary data...</Text>
        </Group>
      </Box>
    );
  }

  if (error) {
    return (
      <Box p="md">
        <Paper p="md" withBorder color="red">
          <Text color="red">Error: {error}</Text>
        </Paper>
      </Box>
    );
  }

  // Calculate aggregated metrics
  const aggregatedData = summaries.reduce((acc, curr) => {
    return {
      sensors: {
        total: curr.sensors.total,
        online: Math.max(acc.sensors.online, curr.sensors.online),
        offline: Math.max(acc.sensors.offline, curr.sensors.offline),
        degraded: Math.max(acc.sensors.degraded, curr.sensors.degraded),
      },
      devices: {
        total: curr.devices.total,
        online: Math.max(acc.devices.online, curr.devices.online),
        offline: Math.max(acc.devices.offline, curr.devices.offline),
        degraded: Math.max(acc.devices.degraded, curr.devices.degraded),
      },
      metrics: {
        avg_pcap_minutes: acc.metrics.avg_pcap_minutes + curr.metrics.avg_pcap_minutes,
        avg_disk_usage_pct: acc.metrics.avg_disk_usage_pct + curr.metrics.avg_disk_usage_pct,
      },
      performance: {
        avg_processing_time: acc.performance.avg_processing_time + (curr.performance_metrics.avg_processing_time || 0),
        peak_memory_mb: Math.max(acc.performance.peak_memory_mb, curr.performance_metrics.peak_memory_mb || 0),
        unique_subnets: Math.max(acc.performance.unique_subnets, curr.performance_metrics.unique_subnets || 0),
      },
      count: acc.count + 1,
    };
  }, {
    sensors: { total: 0, online: 0, offline: 0, degraded: 0 },
    devices: { total: 0, online: 0, offline: 0, degraded: 0 },
    metrics: { avg_pcap_minutes: 0, avg_disk_usage_pct: 0 },
    performance: { avg_processing_time: 0, peak_memory_mb: 0, unique_subnets: 0 },
    count: 0,
  });

  // Calculate averages
  if (aggregatedData.count > 0) {
    aggregatedData.metrics.avg_pcap_minutes /= aggregatedData.count;
    aggregatedData.metrics.avg_disk_usage_pct /= aggregatedData.count;
    aggregatedData.performance.avg_processing_time /= aggregatedData.count;
  }

  const timeRange = summaries.length > 0 ? {
    start: new Date(summaries[summaries.length - 1].timestamp),
    end: new Date(summaries[0].timestamp),
  } : null;

  return (
    <>
      <Box p="md">
        <Stack spacing="md">
          <Group position="apart">
            <Title order={2}>Sensor Health Summary</Title>
            <Box>
              <Text size="sm" mb={3}>Auto-refresh</Text>
              <Group gap="xs" align="center" style={{ height: 36 }}>
                <Select
                  value={refreshInterval}
                  onChange={val => setRefreshInterval(val || '60')}
                  data={[
                    { value: '30', label: '30 seconds' },
                    { value: '60', label: '1 minute' },
                    { value: '300', label: '5 minutes' }
                  ]}
                  styles={{ input: { height: 36 } }}
                />
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
              </Group>
            </Box>
          </Group>

          <Grid>
            {/* Sensors Status */}
            <Grid.Col span={6}>
              <Card withBorder>
                <Stack>
                  <Title order={3}>Sensors Status</Title>
                  <Group position="apart" align="flex-start">
                    <Stack spacing="xs">
                      <Group spacing="xs" noWrap>
                        <Text size="sm" w={70}>Online</Text>
                        <Badge size="lg" color="green">{aggregatedData.sensors.online}</Badge>
                      </Group>
                      <Group spacing="xs" noWrap>
                        <Text size="sm" w={70}>Offline</Text>
                        <Badge size="lg" color="red">{aggregatedData.sensors.offline}</Badge>
                      </Group>
                      <Group spacing="xs" noWrap>
                        <Text size="sm" w={70}>Degraded</Text>
                        <Badge size="lg" color="yellow">{aggregatedData.sensors.degraded}</Badge>
                      </Group>
                    </Stack>
                    <RingProgress
                      size={120}
                      thickness={12}
                      label={
                        <Text size="xs" align="center">
                          {aggregatedData.sensors.total}
                          <Text size="xs" color="dimmed">Total</Text>
                        </Text>
                      }
                      sections={[
                        { value: (aggregatedData.sensors.online / aggregatedData.sensors.total) * 100, color: 'green', tooltip: `Online: ${aggregatedData.sensors.online}` },
                        { value: (aggregatedData.sensors.offline / aggregatedData.sensors.total) * 100, color: 'red', tooltip: `Offline: ${aggregatedData.sensors.offline}` },
                        { value: (aggregatedData.sensors.degraded / aggregatedData.sensors.total) * 100, color: 'yellow', tooltip: `Degraded: ${aggregatedData.sensors.degraded}` }
                      ]}
                    />
                  </Group>
                </Stack>
              </Card>
            </Grid.Col>

            {/* Devices Status */}
            <Grid.Col span={6}>
              <Card withBorder>
                <Stack>
                  <Title order={3}>Devices Status</Title>
                  <Group position="apart" align="flex-start">
                    <Stack spacing="xs">
                      <Group spacing="xs" noWrap>
                        <Text size="sm" w={70}>Online</Text>
                        <Badge size="lg" color="green">{aggregatedData.devices.online}</Badge>
                      </Group>
                      <Group spacing="xs" noWrap>
                        <Text size="sm" w={70}>Offline</Text>
                        <Badge size="lg" color="red">{aggregatedData.devices.offline}</Badge>
                      </Group>
                      <Group spacing="xs" noWrap>
                        <Text size="sm" w={70}>Degraded</Text>
                        <Badge size="lg" color="yellow">{aggregatedData.devices.degraded}</Badge>
                      </Group>
                    </Stack>
                    <RingProgress
                      size={120}
                      thickness={12}
                      label={
                        <Text size="xs" align="center">
                          {aggregatedData.devices.total}
                          <Text size="xs" color="dimmed">Total</Text>
                        </Text>
                      }
                      sections={[
                        { value: (aggregatedData.devices.online / aggregatedData.devices.total) * 100, color: 'green', tooltip: `Online: ${aggregatedData.devices.online}` },
                        { value: (aggregatedData.devices.offline / aggregatedData.devices.total) * 100, color: 'red', tooltip: `Offline: ${aggregatedData.devices.offline}` },
                        { value: (aggregatedData.devices.degraded / aggregatedData.devices.total) * 100, color: 'yellow', tooltip: `Degraded: ${aggregatedData.devices.degraded}` }
                      ]}
                    />
                  </Group>
                </Stack>
              </Card>
            </Grid.Col>

            {/* Location Health Summary */}
            <Grid.Col span={12}>
              <Card withBorder>
                <Stack>
                  <Title order={3}>Location Health Summary</Title>
                  <Table>
                    <thead>
                      <tr>
                        <th>Location</th>
                        <th>Sensors</th>
                        <th>Devices</th>
                        <th>Network Coverage</th>
                        <th>Storage</th>
                        <th>Health Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summaries[0]?.performance_metrics?.location_stats && 
                        Object.entries(summaries[0].performance_metrics.location_stats)
                          .sort(([locA], [locB]) => locA.localeCompare(locB))
                          .map(([location, stats]: [string, any]) => {
                        const totalSensors = (stats.sensors_online || 0) + (stats.sensors_offline || 0);
                        const totalDevices = (stats.devices_online || 0) + (stats.devices_offline || 0);
                        
                        let healthScore = 0;
                        if (totalSensors > 0) {
                          // First check if sensors are online
                          const sensorScore = ((stats.sensors_online || 0) / totalSensors) * 100;
                          
                          // Then check if all devices for online sensors are also online
                          const deviceScore = stats.sensors_online > 0 ? 
                            ((stats.devices_online || 0) / (stats.devices_online + stats.devices_offline)) * 100 : 0;
                          
                          // A location is only 100% healthy if all sensors are online AND all their devices are online
                          healthScore = Math.round(
                            (sensorScore + deviceScore) / 2
                          );
                        }
                        
                        return (
                          <tr key={location}>
                            <td>{location}</td>
                            <td>
                              <Group spacing={4}>
                                <Badge 
                                  color={stats.sensors_online > 0 ? 'green' : 'gray.7'} 
                                  size="sm"
                                  variant={stats.sensors_online > 0 ? 'filled' : 'light'}
                                >
                                  {stats.sensors_online || 0} online
                                </Badge>
                                <Badge 
                                  color={stats.sensors_offline > 0 ? 'red' : 'gray.7'} 
                                  size="sm"
                                  variant={stats.sensors_offline > 0 ? 'filled' : 'light'}
                                >
                                  {stats.sensors_offline || 0} offline
                                </Badge>
                                <Text size="xs" c="dimmed">Total: {(stats.sensors_online || 0) + (stats.sensors_offline || 0)}</Text>
                              </Group>
                            </td>
                            <td>
                              <Group spacing={4}>
                                <Badge 
                                  color={stats.devices_online > 0 ? 'green' : 'gray.7'} 
                                  size="sm"
                                  variant={stats.devices_online > 0 ? 'filled' : 'light'}
                                >
                                  {stats.devices_online || 0} online
                                </Badge>
                                <Badge 
                                  color={stats.devices_offline > 0 ? 'red' : 'gray.7'} 
                                  size="sm"
                                  variant={stats.devices_offline > 0 ? 'filled' : 'light'}
                                >
                                  {stats.devices_offline || 0} offline
                                </Badge>
                                <Text size="xs" c="dimmed">Total: {stats.devices_online + stats.devices_offline}</Text>
                              </Group>
                            </td>
                            <td>
                              <Text size="sm">{stats.unique_subnets || 0} subnets</Text>
                            </td>
                            <td>
                              <Group spacing={4}>
                                <Text size="sm">PCAP: {Math.round((stats.pcap_minutes || 0) / 60)}h</Text>
                              </Group>
                            </td>
                            <td>
                              <Badge 
                                color={healthScore > 80 ? 'green' : healthScore > 60 ? 'yellow' : 'red'}
                                size="md"
                              >
                                {healthScore}%
                              </Badge>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </Table>
                </Stack>
              </Card>
            </Grid.Col>

            {/* Performance Metrics */}
            <Grid.Col span={12}>
              <Card withBorder>
                <Stack>
                  <Title order={3}>Performance Metrics</Title>
                  <Grid>
                    <Grid.Col span={3}>
                      <Stack align="center">
                        <Title order={4}>Avg PCAP Time</Title>
                        <Text size="xl">{Math.round(aggregatedData.metrics.avg_pcap_minutes)}m</Text>
                      </Stack>
                    </Grid.Col>
                    <Grid.Col span={3}>
                      <Stack align="center">
                        <Title order={4}>Disk Usage</Title>
                        <Text size="xl">{Math.round(aggregatedData.metrics.avg_disk_usage_pct)}%</Text>
                      </Stack>
                    </Grid.Col>
                    <Grid.Col span={3}>
                      <Stack align="center">
                        <Title order={4}>Processing Time</Title>
                        <Text size="xl">{aggregatedData.performance.avg_processing_time.toFixed(2)}s</Text>
                      </Stack>
                    </Grid.Col>
                    <Grid.Col span={3}>
                      <Stack align="center">
                        <Title order={4}>Peak Memory</Title>
                        <Text size="xl">{Math.round(aggregatedData.performance.peak_memory_mb)} MB</Text>
                      </Stack>
                    </Grid.Col>
                  </Grid>
                </Stack>
              </Card>
            </Grid.Col>

            {/* System Health Trends */}
            <Grid.Col span={12}>
              <Card withBorder>
                <Stack>
                  <Title order={3}>System Health Trends</Title>
                  <Grid>
                    <Grid.Col span={6}>
                      <Stack align="center">
                        <Title order={4}>Network Activity</Title>
                        <Group spacing="xl">
                          <Stack align="center">
                            <Text size="sm" color="dimmed">Unique Subnets</Text>
                            <Text size="xl">{aggregatedData.performance.unique_subnets}</Text>
                          </Stack>
                          <Stack align="center">
                            <Text size="sm" color="dimmed">Avg Processing</Text>
                            <Text size="xl">{aggregatedData.performance.avg_processing_time.toFixed(1)}s</Text>
                          </Stack>
                        </Group>
                      </Stack>
                    </Grid.Col>
                    <Grid.Col span={6}>
                      <Stack align="center">
                        <Title order={4}>Storage Health</Title>
                        <Group spacing="xl">
                          <Stack align="center">
                            <Text size="sm" color="dimmed">PCAP Retention</Text>
                            <Text size="xl">{Math.round(aggregatedData.metrics.avg_pcap_minutes / 60)}h</Text>
                          </Stack>
                          <Stack align="center">
                            <Text size="sm" color="dimmed">Disk Usage</Text>
                            <Text size="xl" color={aggregatedData.metrics.avg_disk_usage_pct > 80 ? 'red' : aggregatedData.metrics.avg_disk_usage_pct > 60 ? 'yellow' : 'green'}>
                              {Math.round(aggregatedData.metrics.avg_disk_usage_pct)}%
                            </Text>
                          </Stack>
                        </Group>
                      </Stack>
                    </Grid.Col>
                  </Grid>
                </Stack>
              </Card>
            </Grid.Col>

          </Grid>
        </Stack>
      </Box>

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
    </>
  );
} 
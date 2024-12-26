import { useState, useEffect } from 'react';
import { Box, Title, Text, Badge, Group, Stack, Card, Loader, Select, RingProgress, Tooltip, Paper, Grid, Table } from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import apiService from '../../services/api';
import type { HealthSummary } from '../../services/api';

export function HealthSummaryPage() {
  const [summaries, setSummaries] = useState<HealthSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startTime, setStartTime] = useState<Date | null>(null);
  const [endTime, setEndTime] = useState<Date | null>(null);
  const [refreshInterval, setRefreshInterval] = useState<string>('30');
  const [refreshProgress, setRefreshProgress] = useState(100);

  const fetchSummaries = async () => {
    try {
      setLoading(true);
      const params: { start_time?: string; end_time?: string } = {};
      if (startTime) params.start_time = startTime.toISOString();
      if (endTime) params.end_time = endTime.toISOString();
      
      const response = await apiService.getHealthSummary(params);
      setSummaries(response.summaries || []);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching health summaries:', err);
      setError(err.message || 'Failed to fetch health summary data');
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchSummaries();
  }, [startTime, endTime]);

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
    <Box p="md">
      <Stack spacing="md">
        <Group position="apart">
          <Title order={2}>Sensor Health Summary</Title>
          <Group>
            <DateTimePicker
              label="Start Time"
              placeholder="Select start time"
              value={startTime}
              onChange={setStartTime}
              clearable
            />
            <DateTimePicker
              label="End Time"
              placeholder="Select end time"
              value={endTime}
              onChange={setEndTime}
              clearable
            />
            <Select
              label="Auto-refresh"
              value={refreshInterval}
              onChange={val => setRefreshInterval(val || '30')}
              data={[
                { value: '0', label: 'Disabled' },
                { value: '30', label: '30 seconds' },
                { value: '60', label: '1 minute' },
                { value: '300', label: '5 minutes' }
              ]}
            />
            {refreshInterval !== '0' && (
              <RingProgress
                size={40}
                thickness={4}
                roundCaps
                sections={[{ value: refreshProgress, color: 'blue' }]}
              />
            )}
          </Group>
        </Group>

        {timeRange && (
          <Text size="sm" color="dimmed">
            Showing data from {timeRange.start.toLocaleString()} to {timeRange.end.toLocaleString()}
          </Text>
        )}

        <Grid>
          {/* Sensors Status */}
          <Grid.Col span={6}>
            <Card withBorder>
              <Stack>
                <Title order={3}>Sensors Status</Title>
                <Group position="center">
                  <RingProgress
                    size={200}
                    thickness={20}
                    label={
                      <Text size="xl" align="center">
                        {aggregatedData.sensors.total}
                        <Text size="sm" color="dimmed">Total</Text>
                      </Text>
                    }
                    sections={[
                      { value: (aggregatedData.sensors.online / aggregatedData.sensors.total) * 100, color: 'green', tooltip: `Online: ${aggregatedData.sensors.online}` },
                      { value: (aggregatedData.sensors.offline / aggregatedData.sensors.total) * 100, color: 'red', tooltip: `Offline: ${aggregatedData.sensors.offline}` },
                      { value: (aggregatedData.sensors.degraded / aggregatedData.sensors.total) * 100, color: 'yellow', tooltip: `Degraded: ${aggregatedData.sensors.degraded}` },
                    ]}
                  />
                </Group>
                <Group position="center" spacing="xs">
                  <Badge color="green">Online: {aggregatedData.sensors.online}</Badge>
                  <Badge color="red">Offline: {aggregatedData.sensors.offline}</Badge>
                  <Badge color="yellow">Degraded: {aggregatedData.sensors.degraded}</Badge>
                </Group>
              </Stack>
            </Card>
          </Grid.Col>

          {/* Devices Status */}
          <Grid.Col span={6}>
            <Card withBorder>
              <Stack>
                <Title order={3}>Devices Status</Title>
                <Group position="center">
                  <RingProgress
                    size={200}
                    thickness={20}
                    label={
                      <Text size="xl" align="center">
                        {aggregatedData.devices.total}
                        <Text size="sm" color="dimmed">Total</Text>
                      </Text>
                    }
                    sections={[
                      { value: (aggregatedData.devices.online / aggregatedData.devices.total) * 100, color: 'green', tooltip: `Online: ${aggregatedData.devices.online}` },
                      { value: (aggregatedData.devices.offline / aggregatedData.devices.total) * 100, color: 'red', tooltip: `Offline: ${aggregatedData.devices.offline}` },
                      { value: (aggregatedData.devices.degraded / aggregatedData.devices.total) * 100, color: 'yellow', tooltip: `Degraded: ${aggregatedData.devices.degraded}` },
                    ]}
                  />
                </Group>
                <Group position="center" spacing="xs">
                  <Badge color="green">Online: {aggregatedData.devices.online}</Badge>
                  <Badge color="red">Offline: {aggregatedData.devices.offline}</Badge>
                  <Badge color="yellow">Degraded: {aggregatedData.devices.degraded}</Badge>
                </Group>
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
                  <Grid.Col span={4}>
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
                  <Grid.Col span={4}>
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
                  <Grid.Col span={4}>
                    <Stack align="center">
                      <Title order={4}>System Resources</Title>
                      <Group spacing="xl">
                        <Stack align="center">
                          <Text size="sm" color="dimmed">Peak Memory</Text>
                          <Text size="xl">{Math.round(aggregatedData.performance.peak_memory_mb)} MB</Text>
                        </Stack>
                        <Stack align="center">
                          <Text size="sm" color="dimmed">Active Jobs</Text>
                          <Text size="xl">{summaries[0]?.performance_metrics?.active_jobs || 0}</Text>
                        </Stack>
                      </Group>
                    </Stack>
                  </Grid.Col>
                </Grid>
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
                      <th>PCAP Retention</th>
                      <th>Storage</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(summaries[0]?.performance_metrics?.location_stats || {}).map(([location, stats]: [string, any]) => (
                      <tr key={location}>
                        <td>{location}</td>
                        <td>
                          <Group spacing="xs">
                            <Badge color="green" size="sm">{stats.sensors_online || 0}</Badge>
                            <Badge color="red" size="sm">{stats.sensors_offline || 0}</Badge>
                          </Group>
                        </td>
                        <td>
                          <Group spacing="xs">
                            <Badge color="green" size="sm">{stats.devices_online || 0}</Badge>
                            <Badge color="red" size="sm">{stats.devices_offline || 0}</Badge>
                          </Group>
                        </td>
                        <td>{Math.round((stats.pcap_minutes || 0) / 60)}h</td>
                        <td>
                          <Text color={stats.disk_usage > 80 ? 'red' : stats.disk_usage > 60 ? 'yellow' : 'green'}>
                            {stats.disk_usage || 0}%
                          </Text>
                        </td>
                        <td>
                          <Badge 
                            color={stats.health_score > 80 ? 'green' : stats.health_score > 60 ? 'yellow' : 'red'}
                          >
                            {stats.health_score || 0}%
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Stack>
            </Card>
          </Grid.Col>

          {/* Recent Events */}
          <Grid.Col span={12}>
            <Card withBorder>
              <Stack>
                <Title order={3}>System Events</Title>
                <Table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Type</th>
                      <th>Location</th>
                      <th>Description</th>
                      <th>Impact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summaries[0]?.performance_metrics?.recent_events?.slice(0, 5).map((event: any, index: number) => (
                      <tr key={index}>
                        <td>{new Date(event.timestamp).toLocaleTimeString()}</td>
                        <td>
                          <Badge 
                            color={event.type === 'error' ? 'red' : event.type === 'warning' ? 'yellow' : 'blue'}
                          >
                            {event.type}
                          </Badge>
                        </td>
                        <td>{event.location}</td>
                        <td>{event.description}</td>
                        <td>
                          <Badge 
                            color={event.impact === 'high' ? 'red' : event.impact === 'medium' ? 'yellow' : 'green'}
                          >
                            {event.impact}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Stack>
            </Card>
          </Grid.Col>

        </Grid>
      </Stack>
    </Box>
  );
} 
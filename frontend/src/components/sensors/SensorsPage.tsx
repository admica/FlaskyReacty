// PATH: src/components/sensors/SensorsPage.tsx

import { useState, useEffect, useRef } from 'react';
import { Box, Table, Title, Text, Badge, Group, Stack, Card, MultiSelect, Loader, Modal, Select, RingProgress, Tooltip, Paper, ScrollArea, ActionIcon } from '@mantine/core';
import { IconChevronUp, IconChevronDown, IconSelector } from '@tabler/icons-react';
import { formatDistanceToNow, intervalToDuration } from 'date-fns';
import apiService from '../../services/api';

interface Sensor {
  name: string;
  fqdn: string;
  status: string;
  pcap_avail: string;
  totalspace: string;
  usedspace: string;
  last_update: string;
  version: string | null;
  location: string;
}

interface ApiSensor {
  name: string;
  fqdn: string;
  status: string;
  pcap_avail: number;
  totalspace: number;
  usedspace: number;
  last_update: string;
  version?: string;
  location: string;
}

interface ApiDevice {
  name: string;
  port: number;
  type: string;
  status: string;
  last_checked: string;
  runtime: number;
  workers: number;
  src_subnets: number;
  dst_subnets: number;
  uniq_subnets: number;
  avg_idle_time: number;
  avg_work_time: number;
  overflows: number;
  size: string;
  version: string;
}

interface Device {
  name: string;
  port: number;
  type: string;
  status: string;
  last_checked: string;
  runtime: number;
  workers: number;
  src_subnets: number;
  dst_subnets: number;
  uniq_subnets: number;
  avg_idle_time: number;
  avg_work_time: number;
  overflows: number;
  size: string;
  version: string;
}

interface DebugMessage {
  id: number;
  message: string;
  timestamp: string;
}

type SortField = keyof Sensor;

export function SensorsPage() {
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [selectedSensor, setSelectedSensor] = useState<string | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [refreshInterval, setRefreshInterval] = useState<string>('30');
  const [refreshProgress, setRefreshProgress] = useState(100);
  const [showDebug, setShowDebug] = useState(false);
  const [debugMessages, setDebugMessages] = useState<DebugMessage[]>([]);
  const messageIdCounter = useRef(0);

  // Get unique statuses and locations for filters
  const uniqueStatuses = [...new Set(sensors.map(s => s.status))];
  const uniqueLocations = [...new Set(sensors.map(s => s.location).filter(Boolean))];

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

  const fetchSensors = async () => {
    try {
      addDebugMessage('Fetching sensors data...');
      const response = await apiService.getSensors();
      const mappedSensors: Sensor[] = (response.sensors as ApiSensor[]).map(s => ({
        name: s.name,
        fqdn: s.fqdn,
        status: s.status,
        location: s.location,
        version: s.version || null,
        pcap_avail: s.pcap_avail.toString(),
        usedspace: s.usedspace.toString(),
        totalspace: s.totalspace.toString(),
        last_update: s.last_update
      }));
      setSensors(mappedSensors);
      addDebugMessage(`Successfully fetched ${mappedSensors.length} sensors`);
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      addDebugMessage(`Error fetching sensors: ${errorMessage}`);
      setError('Failed to fetch sensors data');
      console.error('Error fetching sensors:', err);
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchSensors();
  }, []);

  // Auto-refresh setup
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
      fetchSensors();
    }, interval * 1000);

    return () => {
      clearInterval(progressTimer);
      clearInterval(refreshTimer);
    };
  }, [refreshInterval]);

  useEffect(() => {
    const fetchDevices = async () => {
      if (!selectedSensor) {
        setDevices([]);
        return;
      }

      setLoadingDevices(true);
      addDebugMessage(`Fetching devices for sensor: ${selectedSensor}`);
      try {
        const response = await apiService.getSensorDevices(selectedSensor);
        const mappedDevices: Device[] = (response.devices as ApiDevice[]).map(d => ({
          name: d.name,
          port: d.port,
          type: d.type,
          status: d.status,
          last_checked: d.last_checked,
          runtime: d.runtime,
          workers: d.workers,
          src_subnets: d.src_subnets,
          dst_subnets: d.dst_subnets,
          uniq_subnets: d.uniq_subnets,
          avg_idle_time: d.avg_idle_time,
          avg_work_time: d.avg_work_time,
          overflows: d.overflows,
          size: d.size,
          version: d.version
        }));
        setDevices(mappedDevices);
        addDebugMessage(`Successfully fetched ${mappedDevices.length} devices for ${selectedSensor}`);
      } catch (err) {
        const errorMessage = typeof err === 'string' ? err : 'Failed to fetch devices';
        addDebugMessage(`Error fetching devices: ${errorMessage}`);
        console.error('Error fetching devices:', err);
      } finally {
        setLoadingDevices(false);
      }
    };

    fetchDevices();
  }, [selectedSensor]);

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'online':
        return 'green';
      case 'degraded':
        return 'yellow';
      case 'offline':
        return 'red';
      default:
        return 'gray';
    }
  };

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDirection('asc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (sortBy !== field) return <IconSelector size={14} />;
    return sortDirection === 'asc' ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />;
  };

  const filteredSensors = sensors.filter(sensor => {
    const statusMatch = selectedStatuses.length === 0 || selectedStatuses.includes(sensor.status);
    const locationMatch = selectedLocations.length === 0 || selectedLocations.includes(sensor.location);
    return statusMatch && locationMatch;
  });

  const sortedSensors = [...filteredSensors].sort((a, b) => {
    let comparison = 0;
    
    if (sortBy === 'pcap_avail') {
      comparison = parseInt(a[sortBy]) - parseInt(b[sortBy]);
    } else if (sortBy === 'usedspace') {
      comparison = parseInt(a[sortBy]) - parseInt(b[sortBy]);
    } else {
      comparison = String(a[sortBy]).localeCompare(String(b[sortBy]));
    }
    
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  const handleSensorClick = (sensorName: string) => {
    setSelectedSensor(sensorName);
  };

  const handleCloseModal = () => {
    setSelectedSensor(null);
    setDevices([]);
  };

  const getDeviceTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'pcapcollect':
        return 'blue';
      case 'tcpdump':
        return 'grape';
      default:
        return 'gray';
    }
  };

  const formatTimeAgo = (timestamp: string | number, includeSeconds = true) => {
    let seconds: number;
    
    if (typeof timestamp === 'string') {
      // For date strings (last_update)
      seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000);
    } else {
      // For numeric values (runtime, pcap_avail)
      seconds = typeof timestamp === 'string' ? parseInt(timestamp) : timestamp;
    }

    const duration = intervalToDuration({ start: 0, end: seconds * 1000 });
    const { years, months, days, hours, minutes, seconds: secs } = duration;
    
    const parts: string[] = [];
    
    if (years) parts.push(`${years} ${years === 1 ? 'year' : 'years'}`);
    if (months) parts.push(`${months} ${months === 1 ? 'month' : 'months'}`);
    if (days) parts.push(`${days} ${days === 1 ? 'day' : 'days'}`);
    if (hours) parts.push(`${hours} ${hours === 1 ? 'hour' : 'hours'}`);
    if (minutes) parts.push(`${minutes} mins`);
    
    const totalMinutes = seconds / 60;
    if (includeSeconds && totalMinutes < 3 && secs) {
      parts.push(`${secs} secs`);
    }
    
    if (parts.length === 0) {
      return 'less than a second ago';
    }
    
    return parts.join(', ') + ' ago';
  };

  const formatPcapAvailable = (pcap: string) => {
    // If it's "0" or not a number, return as is
    if (pcap === "0" || isNaN(parseInt(pcap))) {
      return pcap;
    }

    // Convert minutes to a duration
    const minutes = parseInt(pcap);
    const duration = intervalToDuration({ start: 0, end: minutes * 60 * 1000 });
    const { days, hours, minutes: mins } = duration;
    
    const parts: string[] = [];
    if (days) parts.push(`${days} ${days === 1 ? 'day' : 'days'}`);
    if (hours) parts.push(`${hours} ${hours === 1 ? 'hour' : 'hours'}`);
    if (mins) parts.push(`${mins} mins`);
    
    return parts.join(', ');
  };

  const getStoragePercentage = (used: string, total: string): number => {
    // Remove 'G' suffix and convert to numbers
    const usedNum = parseFloat(used.replace('G', ''));
    const totalNum = parseFloat(total.replace('G', ''));
    return (usedNum / totalNum) * 100;
  };

  if (loading) {
    return (
      <Stack align="center" justify="center" h="100%">
        <Text>Loading sensors...</Text>
      </Stack>
    );
  }

  if (error) {
    return (
      <Stack align="center" justify="center" h="100%">
        <Text c="red">{error}</Text>
      </Stack>
    );
  }

  return (
    <Box p="md" style={{ position: 'relative' }}>
      <Group justify="space-between" mb="md">
        <Title order={2}>Sensors</Title>
      </Group>

      {/* Filters */}
      <Card withBorder mb="md">
        <Group gap="md">
          <MultiSelect
            label="Filter by Status"
            placeholder="All Statuses"
            data={uniqueStatuses}
            value={selectedStatuses}
            onChange={setSelectedStatuses}
            clearable
          />
          <MultiSelect
            label="Filter by Location"
            placeholder="All Locations"
            data={uniqueLocations}
            value={selectedLocations}
            onChange={setSelectedLocations}
            clearable
          />
          <Box>
            <Text size="sm" mb={3}>Auto-refresh</Text>
            <Group gap="xs" align="center" style={{ height: 36 }}>
              <Select
                value={refreshInterval}
                onChange={(value) => setRefreshInterval(value || '30')}
                data={[
                  { value: '0', label: 'Manual refresh' },
                  { value: '10', label: '10 seconds' },
                  { value: '30', label: '30 seconds' },
                  { value: '60', label: '1 minute' },
                  { value: '300', label: '5 minutes' },
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
          {loading && <Loader size="sm" />}
        </Group>
      </Card>
      
      {/* Sensors Table */}
      <Card withBorder>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th onClick={() => handleSort('location')} style={{ cursor: 'pointer' }}>
                <Group justify="space-between">
                  Location
                  {getSortIcon('location')}
                </Group>
              </Table.Th>
              <Table.Th onClick={() => handleSort('name')} style={{ cursor: 'pointer' }}>
                <Group justify="space-between">
                  Name
                  {getSortIcon('name')}
                </Group>
              </Table.Th>
              <Table.Th onClick={() => handleSort('status')} style={{ cursor: 'pointer' }}>
                <Group justify="space-between">
                  Status
                  {getSortIcon('status')}
                </Group>
              </Table.Th>
              <Table.Th onClick={() => handleSort('pcap_avail')} style={{ cursor: 'pointer' }}>
                <Group justify="space-between">
                  PCAP Available
                  {getSortIcon('pcap_avail')}
                </Group>
              </Table.Th>
              <Table.Th onClick={() => handleSort('last_update')} style={{ cursor: 'pointer' }}>
                <Group justify="space-between">
                  Last Update
                  {getSortIcon('last_update')}
                </Group>
              </Table.Th>
              <Table.Th onClick={() => handleSort('usedspace')} style={{ cursor: 'pointer' }}>
                <Group justify="space-between">
                  Storage Used
                  {getSortIcon('usedspace')}
                </Group>
              </Table.Th>
              <Table.Th onClick={() => handleSort('version')} style={{ cursor: 'pointer' }}>
                <Group justify="space-between">
                  Version
                  {getSortIcon('version')}
                </Group>
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sortedSensors.map((sensor) => (
              <Table.Tr 
                key={sensor.name}
                onClick={() => handleSensorClick(sensor.name)}
                style={{ cursor: 'pointer' }}
              >
                <Table.Td>{sensor.location || 'N/A'}</Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <Text>{sensor.name}</Text>
                    <Text size="xs" c="dimmed">({sensor.fqdn})</Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Badge color={getStatusColor(sensor.status)}>
                    {sensor.status}
                  </Badge>
                </Table.Td>
                <Table.Td>{formatPcapAvailable(sensor.pcap_avail)}</Table.Td>
                <Table.Td>{formatTimeAgo(sensor.last_update)}</Table.Td>
                <Table.Td>
                  <Tooltip
                    label={`${sensor.usedspace} of ${sensor.totalspace}`}
                    position="top"
                  >
                    <Box>
                      <Box
                        style={{
                          width: '100px',
                          height: '16px',
                          backgroundColor: 'var(--mantine-color-gray-6)',
                          borderRadius: '6px',
                          overflow: 'hidden'
                        }}
                      >
                        <Box
                          style={{
                            width: `${getStoragePercentage(sensor.usedspace, sensor.totalspace)}%`,
                            height: '100%',
                            backgroundColor: 'var(--mantine-color-blue-5)',
                            transition: 'width 0.3s ease'
                          }}
                        />
                      </Box>
                    </Box>
                  </Tooltip>
                </Table.Td>
                <Table.Td>{sensor.version || 'N/A'}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>

      {/* Device Details Modal */}
      <Modal
        opened={!!selectedSensor}
        onClose={handleCloseModal}
        title={
          <Group>
            <Title order={3}>Devices for {selectedSensor}</Title>
            <Badge size="lg">{devices.length} devices</Badge>
          </Group>
        }
        size="90%"
        centered
      >
        {loadingDevices ? (
          <Stack align="center" py="xl">
            <Loader />
            <Text>Loading devices...</Text>
          </Stack>
        ) : (
          <Table striped horizontalSpacing="md" verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Last Checked</Table.Th>
                <Table.Th>Runtime</Table.Th>
                <Table.Th>Subnets</Table.Th>
                <Table.Th>Performance</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Version</Table.Th>
                <Table.Th>Workers</Table.Th>
                <Table.Th>Port</Table.Th>
                <Table.Th>Filesize</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {devices.map((device) => (
                <Table.Tr key={device.name}>
                  <Table.Td>
                    <Text size="sm" fw={500}>
                      {device.name}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={getStatusColor(device.status)}>
                      {device.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {formatDistanceToNow(new Date(device.last_checked), { addSuffix: true })}
                  </Table.Td>
                  <Table.Td>
                    {formatTimeAgo(device.runtime)}
                  </Table.Td>
                  <Table.Td>
                    <Stack gap="2">
                      <Text size="xs" c="dimmed">src: {device.src_subnets}</Text>
                      <Text size="xs" c="dimmed">dst: {device.dst_subnets}</Text>
                      <Text size="xs" c="dimmed">uniq: {device.uniq_subnets}</Text>
                    </Stack>
                  </Table.Td>
                  <Table.Td>
                    <Stack gap="2">
                      <Text size="xs" c="dimmed">idle: {device.avg_idle_time}ms</Text>
                      <Text size="xs" c="dimmed">work: {device.avg_work_time === 0 ? '<1' : device.avg_work_time}ms</Text>
                      <Text size="xs" c="dimmed">overflows: {device.overflows}</Text>
                    </Stack>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={getDeviceTypeColor(device.type)} variant="light">
                      {device.type}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{device.version}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{device.workers}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{device.port}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{device.size}</Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Modal>

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
                    <Text span c="dimmed" size="xs" style={{ userSelect: 'text' }}>[{new Date(msg.timestamp).toLocaleTimeString()}]</Text>{' '}
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
    </Box>
  );
} 

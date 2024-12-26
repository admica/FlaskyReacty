import { useEffect, useState } from 'react';
import { Box, Group, Select, RingProgress, Text, Button } from '@mantine/core';
import { IconRefresh } from '@tabler/icons-react';

interface RefreshControlProps {
  lastRefresh: Date;
  refreshInterval: number;
  onRefreshIntervalChange: (value: number) => void;
  isRefreshing: boolean;
  onRefresh: () => void;
}

export function RefreshControl({
  lastRefresh,
  refreshInterval,
  onRefreshIntervalChange,
  isRefreshing,
  onRefresh
}: RefreshControlProps) {
  const [refreshProgress, setRefreshProgress] = useState(100);

  useEffect(() => {
    if (refreshInterval === 0) {
      setRefreshProgress(100);
      return;
    }

    const progressInterval = 100; // Update every 100ms
    const steps = refreshInterval * 1000 / progressInterval;
    const decrementAmount = 100 / steps;
    
    setRefreshProgress(100);
    
    const progressTimer = setInterval(() => {
      setRefreshProgress(prev => Math.max(0, prev - decrementAmount));
    }, progressInterval);

    return () => {
      clearInterval(progressTimer);
    };
  }, [refreshInterval, lastRefresh]);

  return (
    <Group gap="md">
      <Box>
        <Text size="sm" mb={3}>Auto-refresh</Text>
        <Group gap="xs" align="center" style={{ height: 36 }}>
          <Select
            value={String(refreshInterval)}
            onChange={(value) => onRefreshIntervalChange(Number(value || 60))}
            data={[
              { value: '0', label: 'Manual refresh' },
              { value: '15', label: '15 seconds' },
              { value: '30', label: '30 seconds' },
              { value: '60', label: '1 minute' },
              { value: '300', label: '5 minutes' },
            ]}
            styles={{ input: { height: 36 } }}
          />
          {refreshInterval !== 0 && (
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
        onClick={onRefresh}
        leftSection={<IconRefresh size={20} />}
        style={{ marginTop: 'auto' }}
      >
        Refresh
      </Button>
    </Group>
  );
} 
import { useEffect, useState } from 'react';
import { Card, Table, Title, Badge, Text, Alert, LoadingOverlay, Stack, Group } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { useInterval } from '@mantine/hooks';
import apiService from '../../services/api';
import { RefreshControl } from '../ui/RefreshControl';

interface UserSession {
  username: string;
  created_at: string;
  expires_at: string;
  role: string;
  is_current: boolean;
}

interface UserSessionsResponse {
  sessions: UserSession[];
}

function UserSessionsTable({ users, emptyMessage }: { users: UserSession[], emptyMessage: string }) {
  return (
    <Table striped highlightOnHover verticalSpacing="xs">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Username</Table.Th>
          <Table.Th>Role</Table.Th>
          <Table.Th>Session Started</Table.Th>
          <Table.Th>Session Expires</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {users.map((user) => (
          <Table.Tr key={user.username}>
            <Table.Td>
              <Text size="sm">{user.username}</Text>
            </Table.Td>
            <Table.Td>
              <Badge 
                color={user.role === 'admin' ? 'blue' : 'gray'}
                size="sm"
              >
                {user.role}
              </Badge>
            </Table.Td>
            <Table.Td>
              <Text size="sm">
                {new Date(user.created_at).toLocaleString(undefined, {
                  year: 'numeric',
                  month: 'numeric',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit'
                })}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm">
                {new Date(user.expires_at).toLocaleString(undefined, {
                  year: 'numeric',
                  month: 'numeric',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit'
                })}
              </Text>
            </Table.Td>
          </Table.Tr>
        ))}
        {users.length === 0 && (
          <Table.Tr>
            <Table.Td colSpan={4}>
              <Text ta="center" c="dimmed">{emptyMessage}</Text>
            </Table.Td>
          </Table.Tr>
        )}
      </Table.Tbody>
    </Table>
  );
}

export function UsersPage() {
  const [sessions, setSessions] = useState<UserSessionsResponse>({ sessions: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshInterval, setRefreshInterval] = useState(60); // 1 minute default
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchSessions = async () => {
    try {
      if (!isRefreshing) {
        setLoading(true);
      }
      setIsRefreshing(true);
      setError(null);
      const response = await apiService.getUserSessions();
      console.log('Received sessions:', response);
      setSessions(response);
      setLastRefresh(new Date());
    } catch (err: any) {
      console.error('Failed to fetch user sessions:', err);
      setError(err.message || 'Failed to fetch user sessions');
    } finally {
      setIsRefreshing(false);
      setLoading(false);
    }
  };

  // Set up automatic refresh interval
  const interval = useInterval(fetchSessions, refreshInterval * 1000);
  useEffect(() => {
    interval.start();
    return interval.stop;
  }, [refreshInterval]);

  // Initial fetch
  useEffect(() => {
    fetchSessions();
  }, []);

  // Get the most recent session for each user
  const userLatestSessions = new Map<string, UserSession>();
  sessions.sessions.forEach(session => {
    const existing = userLatestSessions.get(session.username);
    if (!existing || new Date(session.created_at) > new Date(existing.created_at)) {
      userLatestSessions.set(session.username, session);
    }
  });

  // Split into active and recent based on expiration time
  const now = new Date();
  const activeUsers: UserSession[] = [];
  const recentUsers: UserSession[] = [];

  userLatestSessions.forEach(session => {
    if (new Date(session.expires_at) > now) {
      activeUsers.push(session);
    } else {
      recentUsers.push(session);
    }
  });

  return (
    <Stack gap="lg">
      <Card withBorder pos="relative">
        <LoadingOverlay visible={loading} />
        <Group justify="space-between" mb="md">
          <Title order={2}>Active Users</Title>
          <RefreshControl
            lastRefresh={lastRefresh}
            refreshInterval={refreshInterval}
            onRefreshIntervalChange={setRefreshInterval}
            isRefreshing={isRefreshing}
            onRefresh={fetchSessions}
          />
        </Group>
        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">
            {error}
          </Alert>
        )}
        <UserSessionsTable 
          users={activeUsers} 
          emptyMessage="No active users"
        />
      </Card>

      <Card withBorder>
        <Title order={2} mb="md">Recently Active Users</Title>
        <UserSessionsTable 
          users={recentUsers} 
          emptyMessage="No recently active users"
        />
      </Card>
    </Stack>
  );
} 
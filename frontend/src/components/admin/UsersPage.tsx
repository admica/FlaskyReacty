import { useEffect, useState } from 'react';
import { Card, Table, Title, Badge, Text, Alert, LoadingOverlay, Stack } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import apiService from '../../services/api';

interface UserSession {
  username: string;
  session_start: string;
  session_expires: string;
  role: string;
}

interface UserSessionsResponse {
  active_users: UserSession[];
  recent_users: UserSession[];
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
              <Text size="sm">{new Date(user.session_start).toLocaleString()}</Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm">{new Date(user.session_expires).toLocaleString()}</Text>
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
  const [sessions, setSessions] = useState<UserSessionsResponse>({ active_users: [], recent_users: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiService.getUserSessions();
        setSessions(response);
      } catch (err: any) {
        console.error('Failed to fetch user sessions:', err);
        setError(err.message || 'Failed to fetch user sessions');
      } finally {
        setLoading(false);
      }
    };

    fetchSessions();
    const interval = setInterval(fetchSessions, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <Stack gap="lg">
      <Card withBorder pos="relative">
        <LoadingOverlay visible={loading} />
        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">
            {error}
          </Alert>
        )}
        
        <Title order={2} mb="md">Active Users</Title>
        <UserSessionsTable 
          users={sessions.active_users} 
          emptyMessage="No active users"
        />
      </Card>

      <Card withBorder>
        <Title order={2} mb="md">Recently Active Users</Title>
        <UserSessionsTable 
          users={sessions.recent_users} 
          emptyMessage="No recently active users"
        />
      </Card>
    </Stack>
  );
} 
import { useEffect, useState } from 'react';
import { Card, Table, Title, Badge, Text, Alert, LoadingOverlay } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import apiService from '../../services/api';

interface ActiveUser {
  username: string;
  session_start: string;
  session_expires: string;
  role: string;
}

export function UsersPage() {
  const [users, setUsers] = useState<ActiveUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiService.getActiveUsers();
        setUsers(response.active_users);
      } catch (err: any) {
        console.error('Failed to fetch active users:', err);
        setError(err.message || 'Failed to fetch active users');
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
    const interval = setInterval(fetchUsers, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <Title order={2} mb="md">Active Users</Title>
      <Card withBorder pos="relative">
        <LoadingOverlay visible={loading} />
        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">
            {error}
          </Alert>
        )}
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
            {!loading && users.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={4}>
                  <Text ta="center" c="dimmed">No active users</Text>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Card>
    </>
  );
} 
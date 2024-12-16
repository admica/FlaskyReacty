// PATH: src/components/layout/AppLayout.tsx

import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppShell,
  UnstyledButton,
  Stack,
  Text,
  Button,
  Divider,
  Group,
  Avatar,
} from '@mantine/core';
import {
  IconHome,
  IconServer2,
  IconList,
  IconNetwork,
  IconShieldLock,
  IconLogout,
  IconSettings,
} from '@tabler/icons-react';
import apiService from '../../services/api';

interface NavbarLinkProps {
  icon: typeof IconHome;
  label: string;
  active?: boolean;
  onClick?(): void;
}

function NavbarLink({ icon: Icon, label, active, onClick }: NavbarLinkProps) {
  return (
    <UnstyledButton
      onClick={onClick}
      style={{
        display: 'block',
        width: '100%',
        padding: '8px',
        borderRadius: '6px',
        backgroundColor: active ? 'rgba(79, 172, 254, 0.15)' : 'transparent',
        color: active ? '#4facfe' : '#C1C2C5',
        '&:hover': {
          backgroundColor: 'rgba(79, 172, 254, 0.1)',
        },
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <Icon size={24} />
        <Text ml="md">{label}</Text>
      </div>
    </UnstyledButton>
  );
}

const getAvatarColor = (username: string) => {
  // Generate a consistent color based on the username
  const colors = ['blue', 'cyan', 'green', 'yellow', 'orange', 'red', 'pink', 'grape', 'violet', 'indigo'];
  const hash = username.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return colors[hash % colors.length];
};

const navItems = [
  { icon: IconHome, label: 'Dashboard', path: '/dashboard' },
  { icon: IconServer2, label: 'Sensors', path: '/sensors' },
  { icon: IconList, label: 'Jobs', path: '/jobs' },
  { icon: IconNetwork, label: 'Network', path: '/network' },
  { icon: IconSettings, label: 'Preferences', path: '/preferences' },
  { icon: IconShieldLock, label: 'Admin', path: '/admin', adminOnly: true },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();

  const isAdmin = localStorage.getItem('isAdmin') === 'true';
  const username = localStorage.getItem('username');
  const filteredNavItems = navItems.filter(item => !item.adminOnly || isAdmin);

  return (
    <AppShell
      layout="default"
      navbar={{ width: 300, breakpoint: 'sm' }}
      padding="md"
    >
      <AppShell.Navbar p="md">
        <Stack gap="xs" style={{ height: '100%' }}>
          <Stack gap="xs" style={{ flex: 1 }}>
            {filteredNavItems.map((item) => (
              <NavbarLink
                key={item.path}
                icon={item.icon}
                label={item.label}
                active={location.pathname === item.path}
                onClick={() => navigate(item.path)}
              />
            ))}
          </Stack>
          
          <Stack gap="xs">
            <Divider />
            <Group justify="center" gap="sm">
              <Avatar 
                radius="xl" 
                color={username ? getAvatarColor(username) : 'gray'}
                size="md"
              >
                {username ? username[0].toUpperCase() : 'U'}
              </Avatar>
              <div>
                <Text size="sm" fw={500}>
                  {username || 'User'}
                </Text>
                {isAdmin && (
                  <Text size="xs" c="dimmed">
                    Administrator
                  </Text>
                )}
              </div>
            </Group>
            <Button
              variant="light"
              color="red"
              leftSection={<IconLogout size={16} />}
              onClick={() => {
                apiService.logout();
              }}
            >
              Logout
            </Button>
          </Stack>
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main>
        {children}
      </AppShell.Main>
    </AppShell>
  );
} 
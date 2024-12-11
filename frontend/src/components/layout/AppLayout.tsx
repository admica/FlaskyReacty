// PATH: src/components/layout/AppLayout.tsx

import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppShell,
  UnstyledButton,
  Stack,
  Text,
  Button,
  Divider,
} from '@mantine/core';
import {
  IconHome,
  IconServer2,
  IconList,
  IconNetwork,
  IconShieldLock,
  IconLogout,
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

const navItems = [
  { icon: IconHome, label: 'Dashboard', path: '/dashboard' },
  { icon: IconServer2, label: 'Sensors', path: '/sensors' },
  { icon: IconList, label: 'Jobs', path: '/jobs' },
  { icon: IconNetwork, label: 'Network', path: '/network' },
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
            <Text size="sm" c="dimmed" ta="center">
              Logged in as: {username}
            </Text>
            <Button
              variant="light"
              color="red"
              leftSection={<IconLogout size={16} />}
              onClick={() => apiService.logout()}
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
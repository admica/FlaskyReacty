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
  useMantineTheme,
  useMantineColorScheme,
  rgba,
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
import { useState, useEffect } from 'react';
import apiService from '../../services/api';

interface NavbarLinkProps {
  icon: typeof IconHome;
  label: string;
  active?: boolean;
  onClick?(): void;
}

function NavbarLink({ icon: Icon, label, active, onClick }: NavbarLinkProps) {
  const theme = useMantineTheme();
  const { colorScheme } = useMantineColorScheme();
  
  return (
    <UnstyledButton
      onClick={onClick}
      data-active={active || undefined}
      style={{
        display: 'block',
        width: '100%',
        padding: '8px',
        borderRadius: '6px',
        backgroundColor: active ? 
          colorScheme === 'dark' ? 
            rgba(theme.colors.blue[9], 0.25) : 
            rgba(theme.colors.blue[0], 0.35) : 
          'transparent',
        color: active ? 
          colorScheme === 'dark' ? 
            theme.colors.blue[4] : 
            theme.colors.blue[7] : 
          colorScheme === 'dark' ? 
            theme.colors.dark[0] : 
            theme.colors.gray[7],
        '&:hover': {
          backgroundColor: colorScheme === 'dark' ? 
            rgba(theme.colors.blue[9], 0.15) : 
            rgba(theme.colors.blue[0], 0.25),
        },
      }}
    >
      <Group gap="md">
        <Icon size={24} />
        <Text>{label}</Text>
      </Group>
    </UnstyledButton>
  );
}

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
  const [avatarSeed, setAvatarSeed] = useState<number | null>(null);
  const theme = useMantineTheme();

  const isAdmin = localStorage.getItem('isAdmin') === 'true';
  const username = localStorage.getItem('username');
  const filteredNavItems = navItems.filter(item => !item.adminOnly || isAdmin);

  // Load user preferences to get avatar seed
  useEffect(() => {
    const loadPreferences = async () => {
      try {
        const response = await apiService.get('/preferences');
        if (response.data) {
          setAvatarSeed(response.data.avatar_seed);
        }
      } catch (error) {
        console.error('Failed to load preferences:', error);
      }
    };
    loadPreferences();
  }, []);

  return (
    <AppShell
      navbar={{ width: 300, breakpoint: 'sm' }}
    >
      <AppShell.Navbar p="md">
        <Stack gap="xs" h="100%">
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
                size="md"
                src={avatarSeed ? `/api/v1/avatar/${avatarSeed}?username=${username || 'U'}` : undefined}
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
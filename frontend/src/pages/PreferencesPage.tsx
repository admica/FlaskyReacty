import { useState, useEffect } from 'react';
import {
  Container,
  Title,
  Paper,
  Stack,
  Group,
  Text,
  SegmentedControl,
  Switch,
  Button,
  Divider,
  ColorSwatch,
  Avatar,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconMoonStars, IconSun, IconRefresh } from '@tabler/icons-react';
import apiService from '../services/api';

export function PreferencesPage() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [avatarSeed, setAvatarSeed] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Load user preferences when component mounts
    loadUserPreferences();
  }, []);

  const loadUserPreferences = async () => {
    try {
      const response = await apiService.get('/api/v1/preferences');
      if (response.ok) {
        const prefs = await response.json();
        setTheme(prefs.theme || 'dark');
        setAvatarSeed(prefs.avatar_seed);
      }
    } catch (error) {
      console.error('Failed to load preferences:', error);
    }
  };

  const savePreferences = async () => {
    setLoading(true);
    try {
      const response = await apiService.post('/api/v1/preferences', {
        theme,
        avatar_seed: avatarSeed,
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: 'Preferences saved successfully',
          color: 'green',
        });
        localStorage.setItem('theme', theme);
      } else {
        throw new Error('Failed to save preferences');
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to save preferences',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const regenerateAvatar = () => {
    setAvatarSeed(Math.floor(Math.random() * 1000000));
  };

  return (
    <Container size="md">
      <Title order={2} mb="lg">User Preferences</Title>

      <Paper withBorder p="md" radius="md">
        <Stack gap="lg">
          <div>
            <Text fw={500} mb="xs">Theme</Text>
            <SegmentedControl
              value={theme}
              onChange={setTheme}
              data={[
                {
                  value: 'light',
                  label: (
                    <Group gap="xs">
                      <IconSun size={16} />
                      <span>Light</span>
                    </Group>
                  ),
                },
                {
                  value: 'dark',
                  label: (
                    <Group gap="xs">
                      <IconMoonStars size={16} />
                      <span>Dark</span>
                    </Group>
                  ),
                },
              ]}
            />
          </div>

          <Divider />

          <div>
            <Text fw={500} mb="xs">Avatar</Text>
            <Group>
              <Avatar 
                size="xl" 
                radius="xl"
                color="blue"
                src={avatarSeed ? `/api/v1/avatar/${avatarSeed}` : undefined}
              >
                {localStorage.getItem('username')?.[0]?.toUpperCase() || 'U'}
              </Avatar>
              <Button 
                variant="light"
                leftSection={<IconRefresh size={16} />}
                onClick={regenerateAvatar}
              >
                Regenerate Avatar
              </Button>
            </Group>
          </div>

          <Divider />

          <Group justify="flex-end">
            <Button
              onClick={savePreferences}
              loading={loading}
            >
              Save Preferences
            </Button>
          </Group>
        </Stack>
      </Paper>
    </Container>
  );
} 
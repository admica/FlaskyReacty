import { useState, useEffect } from 'react';
import {
  Container,
  Title,
  Paper,
  Stack,
  Group,
  Text,
  SegmentedControl,
  Button,
  Divider,
  Avatar,
} from '@mantine/core';
import { IconMoonStars, IconSun, IconRefresh } from '@tabler/icons-react';
import apiService from '../../services/api';

export function PreferencesPage() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [avatarSeed, setAvatarSeed] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const username = localStorage.getItem('username') || '';

  useEffect(() => {
    loadUserPreferences();
  }, []);

  const loadUserPreferences = async () => {
    try {
      const response = await apiService.get('/preferences');
      console.log('Loaded preferences from backend:', response.data);
      
      if (response.data) {
        setTheme(response.data.theme || 'dark');
        localStorage.setItem('theme', response.data.theme || 'dark');
        setAvatarSeed(response.data.avatar_seed || Math.floor(Math.random() * 1000000));
      }
    } catch (error) {
      console.error('Failed to load preferences:', error);
    }
  };

  const savePreferences = async () => {
    setLoading(true);
    setSaveStatus('idle');
    try {
      const currentSeed = avatarSeed || Math.floor(Math.random() * 1000000);
      setAvatarSeed(currentSeed);

      const response = await apiService.post('/preferences', {
        theme,
        avatar_seed: currentSeed,
        settings: {}
      });

      console.log('Preferences saved successfully to backend');
      localStorage.setItem('theme', theme);
      setSaveStatus('success');
      await loadUserPreferences();
    } catch (error: any) {
      console.error('Failed to save preferences:', error.response?.data?.error || error.message);
      setSaveStatus('error');
    } finally {
      setLoading(false);
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  };

  const handleThemeChange = async (newTheme: string) => {
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    
    try {
      await apiService.post('/preferences', {
        theme: newTheme,
        avatar_seed: avatarSeed,
        settings: {}
      });
      console.log('Theme preference saved to backend');
    } catch (error) {
      console.error('Failed to save theme preference:', error);
    }
  };

  const regenerateAvatar = () => {
    const newSeed = Math.floor(Math.random() * 1000000);
    setAvatarSeed(newSeed);
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
              onChange={handleThemeChange}
              data={[
                {
                  value: 'dark',
                  label: (
                    <Stack gap={2} align="center">
                      <IconMoonStars size={16} />
                      <Text size="sm">Dark</Text>
                    </Stack>
                  ),
                },
                {
                  value: 'light',
                  label: (
                    <Stack gap={2} align="center">
                      <IconSun size={16} />
                      <Text size="sm">Light</Text>
                    </Stack>
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
                src={avatarSeed ? `/api/v1/avatar/${avatarSeed}?username=${username}` : undefined}
              >
                {username[0]?.toUpperCase() || 'U'}
              </Avatar>
              <Button 
                variant="light"
                leftSection={<IconRefresh size={16} />}
                onClick={regenerateAvatar}
                loading={loading}
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
              color={saveStatus === 'success' ? 'green' : saveStatus === 'error' ? 'red' : 'blue'}
            >
              Save Changes
            </Button>
          </Group>
        </Stack>
      </Paper>
    </Container>
  );
} 
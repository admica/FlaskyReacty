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

const getAvatarColor = (seed: number | null) => {
  // Generate color based on the seed instead of username
  const colors = ['blue', 'cyan', 'green', 'yellow', 'orange', 'red', 'pink', 'grape', 'violet', 'indigo'];
  if (seed === null) return 'blue'; // Default color
  return colors[seed % colors.length];
};

export function PreferencesPage() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [avatarSeed, setAvatarSeed] = useState<number>(Math.floor(Math.random() * 1000000));
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState({});
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const username = localStorage.getItem('username') || '';

  // Load preferences from backend when component mounts
  useEffect(() => {
    loadUserPreferences();
  }, []);

  const loadUserPreferences = async () => {
    try {
      const response = await apiService.get('/preferences');
      console.log('Loaded preferences from backend:', response.data);
      
      setTheme(response.data.theme || 'dark');
      // Ensure avatar_seed is never null
      setAvatarSeed(response.data.avatar_seed || Math.floor(Math.random() * 1000000));
      setSettings(response.data.settings || {});
      
      // Update localStorage for theme
      localStorage.setItem('theme', response.data.theme || 'dark');
    } catch (error) {
      console.error('Failed to load preferences:', error);
    }
  };

  const savePreferences = async () => {
    setLoading(true);
    setSaveStatus('idle');
    try {
      // Ensure we have a valid avatar_seed before saving
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
      // Verify the save by reloading preferences
      await loadUserPreferences();
    } catch (error: any) {
      console.error('Failed to save preferences:', error.response?.data?.error || error.message);
      setSaveStatus('error');
    } finally {
      setLoading(false);
      // Reset save status after 3 seconds
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  };

  const handleThemeChange = (newTheme: string) => {
    setTheme(newTheme);
    // Don't save immediately, wait for user to click save
  };

  const regenerateAvatar = () => {
    const newSeed = Math.floor(Math.random() * 1000000);
    setAvatarSeed(newSeed);
    // Don't save immediately, wait for user to click save
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
                color={getAvatarColor(avatarSeed)}
                src={avatarSeed ? `/api/v1/avatar/${avatarSeed}` : undefined}
              >
                {username[0]?.toUpperCase() || 'U'}
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
              color={saveStatus === 'success' ? 'green' : saveStatus === 'error' ? 'red' : 'blue'}
            >
              {saveStatus === 'success' ? 'Saved!' : 
               saveStatus === 'error' ? 'Error Saving' : 
               'Save Preferences'}
            </Button>
          </Group>
        </Stack>
      </Paper>
    </Container>
  );
} 
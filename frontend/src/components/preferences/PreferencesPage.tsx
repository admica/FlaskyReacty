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
  Center,
  Flex,
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
  const [avatarSeed, setAvatarSeed] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const username = localStorage.getItem('username') || '';

  // Load preferences from backend when component mounts
  useEffect(() => {
    loadUserPreferences();
  }, []);

  const loadUserPreferences = async () => {
    try {
      const response = await apiService.get('/api/v1/preferences');
      if (response.ok) {
        const prefs = await response.json();
        console.log('Loaded preferences from backend:', prefs);
        
        // Update both state and localStorage
        setTheme(prefs.theme || 'dark');
        localStorage.setItem('theme', prefs.theme || 'dark');
        
        setAvatarSeed(prefs.avatar_seed);
      } else {
        const errorData = await response.json();
        console.error('Failed to load preferences:', errorData.error);
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
        console.log('Preferences saved successfully to backend');
        // Update localStorage after successful backend save
        localStorage.setItem('theme', theme);
        // Verify the save by reloading preferences
        await loadUserPreferences();
      } else {
        const errorData = await response.json();
        console.error('Failed to save preferences:', errorData.error);
        throw new Error(errorData.error || 'Failed to save preferences');
      }
    } catch (error) {
      console.error('Failed to save preferences:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleThemeChange = async (newTheme: string) => {
    setTheme(newTheme);
    // Save to backend immediately when theme changes
    try {
      const response = await apiService.post('/api/v1/preferences', {
        theme: newTheme,
        avatar_seed: avatarSeed,
      });

      if (response.ok) {
        console.log('Theme preference saved to backend');
        localStorage.setItem('theme', newTheme);
      } else {
        console.error('Failed to save theme preference to backend');
      }
    } catch (error) {
      console.error('Failed to save theme preference:', error);
    }
  };

  const regenerateAvatar = async () => {
    const newSeed = Math.floor(Math.random() * 1000000);
    setAvatarSeed(newSeed);
    
    // Save new avatar seed to backend immediately
    try {
      const response = await apiService.post('/api/v1/preferences', {
        theme,
        avatar_seed: newSeed,
      });

      if (response.ok) {
        console.log('New avatar seed saved to backend');
      } else {
        console.error('Failed to save new avatar seed');
      }
    } catch (error) {
      console.error('Failed to save avatar seed:', error);
    }
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
            >
              Save Preferences
            </Button>
          </Group>
        </Stack>
      </Paper>
    </Container>
  );
} 
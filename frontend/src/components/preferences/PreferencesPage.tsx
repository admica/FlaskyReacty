import { useState, useEffect, useRef } from 'react';
import {
  Paper,
  Stack,
  Group,
  Text,
  SegmentedControl,
  Button,
  Divider,
  Avatar,
  Box,
  ActionIcon,
  ScrollArea,
  Title,
} from '@mantine/core';
import { IconMoonStars, IconSun, IconRefresh } from '@tabler/icons-react';
import apiService from '../../services/api';

interface DebugMessage {
  id: number;
  message: string;
  timestamp: string;
}

export function PreferencesPage() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [avatarSeed, setAvatarSeed] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const username = localStorage.getItem('username') || '';
  
  const [showDebug, setShowDebug] = useState(false);
  const [debugMessages, setDebugMessages] = useState<DebugMessage[]>([]);
  const messageIdCounter = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  const addDebugMessage = (message: string) => {
    setDebugMessages(prev => {
      const updatedMessages = [...prev.slice(-99), {
        id: messageIdCounter.current++,
        timestamp: new Date().toLocaleTimeString(),
        message
      }];
      // Auto-scroll to bottom
      setTimeout(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      }, 100);
      return updatedMessages;
    });
  };

  useEffect(() => {
    (window as any).addDebugMessage = addDebugMessage;
    return () => {
      delete (window as any).addDebugMessage;
    };
  }, []);

  useEffect(() => {
    loadUserPreferences();
  }, []);

  const loadUserPreferences = async () => {
    try {
      addDebugMessage('Loading user preferences...');
      const response = await apiService.get('/preferences');
      addDebugMessage('Loaded preferences from backend: ' + JSON.stringify(response.data));
      
      if (response.data) {
        setTheme(response.data.theme || 'dark');
        localStorage.setItem('theme', response.data.theme || 'dark');
        setAvatarSeed(response.data.avatar_seed || Math.floor(Math.random() * 1000000));
        addDebugMessage('Applied preferences: theme=' + response.data.theme + ', avatar_seed=' + response.data.avatar_seed);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addDebugMessage('Failed to load preferences: ' + errorMessage);
      console.error('Failed to load preferences:', error);
    }
  };

  const savePreferences = async () => {
    setLoading(true);
    setSaveStatus('idle');
    try {
      addDebugMessage('Saving preferences...');
      const currentSeed = avatarSeed || Math.floor(Math.random() * 1000000);
      setAvatarSeed(currentSeed);

      const response = await apiService.post('/preferences', {
        theme,
        avatar_seed: currentSeed,
        settings: {}
      });

      addDebugMessage('Preferences saved successfully');
      localStorage.setItem('theme', theme);
      setSaveStatus('success');
      await loadUserPreferences();
    } catch (error: any) {
      const errorMessage = error.response?.data?.error || error.message;
      addDebugMessage('Failed to save preferences: ' + errorMessage);
      console.error('Failed to save preferences:', errorMessage);
      setSaveStatus('error');
    } finally {
      setLoading(false);
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  };

  const handleThemeChange = async (newTheme: string) => {
    addDebugMessage('Changing theme to: ' + newTheme);
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    
    try {
      await apiService.post('/preferences', {
        theme: newTheme,
        avatar_seed: avatarSeed,
        settings: {}
      });
      addDebugMessage('Theme preference saved to backend');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addDebugMessage('Failed to save theme preference: ' + errorMessage);
      console.error('Failed to save theme preference:', error);
    }
  };

  const regenerateAvatar = () => {
    const newSeed = Math.floor(Math.random() * 1000000);
    addDebugMessage('Regenerating avatar with new seed: ' + newSeed);
    setAvatarSeed(newSeed);
  };

  return (
    <Box pos="relative" pb={50}>
      <Paper p="md">
        <Title order={2} mb="lg">User Preferences</Title>

        <Stack>
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

      <Box
        style={{
          position: 'fixed',
          bottom: 0,
          right: 0,
          width: '200px',
          height: '100px',
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'flex-end',
          padding: '20px',
          zIndex: 1000,
        }}
        onMouseEnter={() => setShowDebug(true)}
      >
        {showDebug ? (
          <Paper
            shadow="md"
            style={{
              position: 'absolute',
              bottom: '20px',
              right: '20px',
              width: '400px',
              background: 'rgba(0, 0, 0, 0.8)',
              backdropFilter: 'blur(4px)',
              border: 'none',
            }}
          >
            <Stack gap="xs" p="xs">
              <Group justify="space-between">
                <Text size="xs" fw={500} c="dimmed">Debug Log ({debugMessages.length} messages)</Text>
                <Group gap="xs">
                  <Text size="xs" c="dimmed">{new Date().toLocaleTimeString()}</Text>
                  <ActionIcon 
                    size="xs" 
                    variant="subtle" 
                    c="dimmed"
                    onClick={() => setShowDebug(false)}
                  >
                    ×
                  </ActionIcon>
                </Group>
              </Group>
              <ScrollArea h={250} scrollbarSize={8} viewportRef={scrollRef}>
                <Stack gap={4}>
                  {debugMessages.map(msg => (
                    <Text key={msg.id} size="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
                      [{msg.timestamp}] {msg.message}
                    </Text>
                  ))}
                </Stack>
              </ScrollArea>
            </Stack>
          </Paper>
        ) : (
          <Box style={{ width: '100%', height: '100%' }} />
        )}
      </Box>
    </Box>
  );
} 
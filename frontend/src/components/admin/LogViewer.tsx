// PATH: src/components/admin/LogViewer.tsx

import { useEffect, useState, useRef } from 'react';
import { Box, Text, ScrollArea } from '@mantine/core';
import api from '../../api/axios';

interface LogViewerProps {
  logFile: string;
}

export function LogViewer({ logFile }: LogViewerProps) {
  const [logLines, setLogLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pollingRef = useRef<NodeJS.Timeout>();

  const fetchLogContent = async () => {
    try {
      const response = await api.get(`/api/v1/logs/${logFile}/content`);
      setLogLines(response.data.content);
      setError(null);
      
      // Auto-scroll to bottom if already at bottom
      if (scrollRef.current) {
        const { scrollHeight, scrollTop, clientHeight } = scrollRef.current;
        const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
        if (isAtBottom) {
          setTimeout(() => {
            if (scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          }, 100);
        }
      }
    } catch (error: any) {
      console.error('Error fetching log content:', error);
      setError(error.response?.data?.error || 'Failed to fetch log content');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    
    // Initial fetch
    fetchLogContent();

    // Set up polling every 5 seconds
    pollingRef.current = setInterval(fetchLogContent, 5000);

    // Cleanup
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [logFile]);

  return (
    <Box>
      {error ? (
        <Text c="red">{error}</Text>
      ) : (
        <ScrollArea h={400} viewportRef={scrollRef}>
          {isLoading ? (
            <Text>Loading log content...</Text>
          ) : logLines.length === 0 ? (
            <Text>No log content available</Text>
          ) : (
            logLines.map((line, index) => (
              <Text key={index} size="sm" style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                {line}
              </Text>
            ))
          )}
        </ScrollArea>
      )}
    </Box>
  );
} 
// PATH: src/components/admin/LogViewer.tsx

import { useEffect, useState, useRef } from 'react';
import { Box, Text, ScrollArea } from '@mantine/core';
import api from '../../api/axios';

interface LogViewerProps {
  logFile: string;
  onDebugMessage?: (message: string) => void;
}

export function LogViewer({ logFile, onDebugMessage }: LogViewerProps) {
  const [logLines, setLogLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pollingRef = useRef<NodeJS.Timeout>();

  const addDebugMessage = (message: string) => {
    console.log('Debug:', message);
    onDebugMessage?.(message);
  };

  const fetchLogContent = async () => {
    try {
      addDebugMessage(`Fetching content for log file: ${logFile}`);
      const response = await api.get(`/logs/${logFile}/content`);
      addDebugMessage(`Received response for ${logFile}`);
      
      if (response.data && Array.isArray(response.data.content)) {
        setLogLines(response.data.content);
        addDebugMessage(`Loaded ${response.data.content.length} lines from ${logFile}`);
        setError(null);
      } else {
        throw new Error('Invalid response format');
      }
      
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
      const errorMessage = error.response?.data?.error || error.message || 'Failed to fetch log content';
      addDebugMessage(`Error fetching ${logFile}: ${errorMessage}`);
      if (error.response) {
        addDebugMessage(`Response status: ${error.response.status}`);
        addDebugMessage(`Response data: ${JSON.stringify(error.response.data)}`);
      }
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    addDebugMessage(`Initializing log viewer for: ${logFile}`);
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
        addDebugMessage(`Cleaned up polling for ${logFile}`);
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
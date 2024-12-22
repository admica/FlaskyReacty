import React from 'react';
import { Button, Stack, Title, Text } from '@mantine/core';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Application Error:', error);
    console.error('Error Info:', errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Stack align="center" justify="center" h="100vh" gap="lg">
          <Title order={2}>Something went wrong</Title>
          <Text c="dimmed">
            {this.state.error?.message || 'An unexpected error occurred'}
          </Text>
          <Button onClick={() => window.location.reload()}>
            Reload Page
          </Button>
        </Stack>
      );
    }

    return this.props.children;
  }
} 
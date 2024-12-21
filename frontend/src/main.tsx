// PATH: src/main.tsx

import React from 'react'
import ReactDOM from 'react-dom/client'
import { MantineProvider, createTheme } from '@mantine/core'
import { ModalsProvider } from '@mantine/modals'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import '@mantine/core/styles.css'
import '@mantine/dates/styles.css'

// Error Boundary Component
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Application Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <h1>Something went wrong.</h1>
          <button onClick={() => window.location.reload()}>Reload Page</button>
        </div>
      );
    }

    return this.props.children;
  }
}

const theme = createTheme({
  primaryColor: 'blue',
  colors: {
    dark: [
      '#C1C2C5', // 0
      '#A6A7AB', // 1
      '#909296', // 2
      '#5c5f66', // 3
      '#373A40', // 4
      '#2C2E33', // 5
      '#25262b', // 6
      '#1A1B1E', // 7
      '#141517', // 8
      '#101113', // 9
    ],
    light: [
      '#F8F9FA', // 0
      '#F1F3F5', // 1
      '#E9ECEF', // 2
      '#DEE2E6', // 3
      '#CED4DA', // 4
      '#ADB5BD', // 5
      '#868E96', // 6
      '#495057', // 7
      '#343A40', // 8
      '#212529', // 9
    ],
  },
  components: {
    AppShell: {
      styles: {
        main: ({ colorScheme, theme }) => ({
          backgroundColor: colorScheme === 'dark' ? theme.colors.dark[7] : theme.colors.light[0],
        }),
        navbar: ({ colorScheme, theme }) => ({
          backgroundColor: colorScheme === 'dark' ? theme.colors.dark[6] : theme.white,
          borderRight: `1px solid ${
            colorScheme === 'dark' ? theme.colors.dark[4] : theme.colors.gray[3]
          }`,
        }),
      },
    },
    Paper: {
      styles: {
        root: ({ colorScheme, theme }) => ({
          backgroundColor: colorScheme === 'dark' ? theme.colors.dark[6] : theme.white,
          color: colorScheme === 'dark' ? theme.white : theme.black,
        }),
      },
    },
    Button: {
      styles: {
        root: ({ colorScheme, theme }) => ({
          '&[data-hover]': {
            backgroundColor: colorScheme === 'dark' 
              ? theme.fn.lighten(theme.colors.dark[6], 0.1)
              : theme.fn.darken(theme.colors.gray[0], 0.1),
          },
        }),
      },
    },
    NavLink: {
      styles: {
        root: ({ colorScheme, theme }) => ({
          '&[data-active]': {
            backgroundColor: colorScheme === 'dark'
              ? theme.fn.rgba(theme.colors.blue[9], 0.25)
              : theme.fn.rgba(theme.colors.blue[0], 0.35),
            color: colorScheme === 'dark'
              ? theme.colors.blue[4]
              : theme.colors.blue[7],
          },
          color: colorScheme === 'dark'
            ? theme.colors.dark[0]
            : theme.colors.gray[7],
          '&:hover': {
            backgroundColor: colorScheme === 'dark'
              ? theme.fn.rgba(theme.colors.blue[9], 0.15)
              : theme.fn.rgba(theme.colors.blue[0], 0.25),
          },
        }),
      },
    },
  },
});

// Get stored theme or system preference
const getInitialColorScheme = () => {
  const storedTheme = localStorage.getItem('theme');
  if (storedTheme) return storedTheme;
  
  const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  return systemPrefersDark ? 'dark' : 'light';
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <MantineProvider theme={theme} defaultColorScheme={getInitialColorScheme()}>
          <ModalsProvider>
            <App />
          </ModalsProvider>
        </MantineProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
) 
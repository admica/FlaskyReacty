// PATH: src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { MantineProvider, createTheme, MantineTheme, MantineColorScheme } from '@mantine/core'
import { ModalsProvider } from '@mantine/modals'
import { Notifications } from '@mantine/notifications'
import { BrowserRouter } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import App from './App'
import './index.css'
import '@mantine/core/styles.css'
import '@mantine/dates/styles.css'
import '@mantine/notifications/styles.css'

interface StyleParams {
  colorScheme: MantineColorScheme;
  theme: MantineTheme;
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
        main: ({ colorScheme, theme }: StyleParams) => ({
          backgroundColor: colorScheme === 'dark' ? theme.colors.dark[7] : theme.colors.light[0],
        }),
        navbar: ({ colorScheme, theme }: StyleParams) => ({
          backgroundColor: colorScheme === 'dark' ? theme.colors.dark[6] : theme.white,
          borderRight: `1px solid ${
            colorScheme === 'dark' ? theme.colors.dark[4] : theme.colors.gray[3]
          }`,
        }),
      },
    },
    Paper: {
      styles: {
        root: ({ colorScheme, theme }: StyleParams) => ({
          backgroundColor: colorScheme === 'dark' ? theme.colors.dark[6] : theme.white,
          color: colorScheme === 'dark' ? theme.white : theme.black,
        }),
      },
    },
    Button: {
      styles: {
        root: ({ colorScheme, theme }: StyleParams) => ({
          '&[data-hover]': {
            backgroundColor: colorScheme === 'dark' 
              ? theme.colors.dark[5]
              : theme.colors.gray[1],
          },
        }),
      },
    },
    NavLink: {
      styles: {
        root: ({ colorScheme, theme }: StyleParams) => ({
          '&[data-active]': {
            backgroundColor: colorScheme === 'dark'
              ? theme.colors.dark[5]
              : theme.colors.blue[0],
            color: colorScheme === 'dark'
              ? theme.colors.blue[4]
              : theme.colors.blue[7],
          },
          color: colorScheme === 'dark'
            ? theme.colors.dark[0]
            : theme.colors.gray[7],
          '&:hover': {
            backgroundColor: colorScheme === 'dark'
              ? theme.colors.dark[6]
              : theme.colors.blue[0],
          },
        }),
      },
    },
  },
});

// Get stored theme or system preference
const getInitialColorScheme = (): MantineColorScheme => {
  const storedTheme = localStorage.getItem('theme');
  if (storedTheme === 'light' || storedTheme === 'dark') return storedTheme;
  
  const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  return systemPrefersDark ? 'dark' : 'light';
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <MantineProvider theme={theme} defaultColorScheme={getInitialColorScheme()}>
          <Notifications position="top-right" />
          <ModalsProvider>
            <App />
          </ModalsProvider>
        </MantineProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
) 
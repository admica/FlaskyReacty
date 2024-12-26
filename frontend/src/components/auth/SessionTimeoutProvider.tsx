// PATH: src/components/auth/SessionTimeoutProvider.tsx
import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Modal, Button, Progress, Text, Group } from '@mantine/core';
import apiService from '../../services/api';

interface SessionContextType {
    logout: () => void;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export const useSession = () => {
    const context = useContext(SessionContext);
    if (!context) {
        throw new Error('useSession must be used within a SessionProvider');
    }
    return context;
};

// Constants for timing (in milliseconds)
const INITIAL_DELAY = 13 * 60 * 1000 + 58 * 1000; // 13 minutes and 58 seconds
const WARNING_TIME = 60 * 1000;                   // 1 minute countdown

// Debug logging function
const debug = (message: string, data?: any) => {
    const timestamp = new Date().toISOString();
    const logMessage = data 
        ? `[SessionTimeout] ${message} | ${JSON.stringify(data)}`
        : `[SessionTimeout] ${message}`;
    console.debug(`${timestamp} ${logMessage}`);
    const debugHandler = (window as any).addDebugMessage;
    if (typeof debugHandler === 'function') {
        debugHandler(logMessage);
    }
};

export function SessionTimeoutProvider({ children }: { children: React.ReactNode }) {
    const [showWarning, setShowWarning] = useState(false);
    const [timeLeft, setTimeLeft] = useState(WARNING_TIME);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const warningTimerRef = useRef<NodeJS.Timeout | null>(null);
    const countdownRef = useRef<NodeJS.Timeout | null>(null);
    const navigate = useNavigate();

    const clearTimers = useCallback(() => {
        debug('Clearing timers');
        if (warningTimerRef.current) {
            clearTimeout(warningTimerRef.current);
            warningTimerRef.current = null;
        }
        if (countdownRef.current) {
            clearInterval(countdownRef.current);
            countdownRef.current = null;
        }
        setTimeLeft(WARNING_TIME);
    }, []);

    const logout = useCallback(async () => {
        debug('Logging out');
        clearTimers();
        setShowWarning(false);
        try {
            await apiService.logout();
            debug('Logout successful');
        } catch (error) {
            debug('Error during logout', { error });
        }
        navigate('/login');
    }, [navigate, clearTimers]);

    const startWarningTimer = useCallback(() => {
        debug('Starting warning timer');
        clearTimers();

        // Show warning after INITIAL_DELAY
        warningTimerRef.current = setTimeout(() => {
            debug('Showing warning popup');
            setShowWarning(true);
            setTimeLeft(WARNING_TIME);

            // Start countdown
            countdownRef.current = setInterval(() => {
                setTimeLeft(prev => {
                    const newTime = prev - 1000;
                    debug('Countdown update', { timeLeft: newTime / 1000 });
                    if (newTime <= 0) {
                        debug('Countdown finished - logging out');
                        clearInterval(countdownRef.current!);
                        countdownRef.current = null;
                        logout();
                        return 0;
                    }
                    return newTime;
                });
            }, 1000);
        }, INITIAL_DELAY);
    }, [clearTimers, logout]);

    const extendSession = useCallback(async () => {
        if (isRefreshing) return;
        
        debug('Extending session');
        setIsRefreshing(true);
        clearTimers();
        setShowWarning(false);
        
        try {
            await apiService.refreshToken();
            debug('Session extended successfully');
            startWarningTimer();
        } catch (error) {
            debug('Failed to extend session', { error });
            logout();
        } finally {
            setIsRefreshing(false);
        }
    }, [isRefreshing, clearTimers, logout, startWarningTimer]);

    // Start timer when component mounts or after login
    useEffect(() => {
        const accessToken = localStorage.getItem('access_token');
        if (accessToken) {
            debug('Access token found - starting session timer');
            startWarningTimer();
        } else {
            debug('No access token found');
        }
        return clearTimers;
    }, [startWarningTimer, clearTimers]);

    return (
        <SessionContext.Provider value={{ logout }}>
            {showWarning && (
                <Modal
                    opened={true}
                    onClose={() => {}}
                    withCloseButton={false}
                    closeOnClickOutside={false}
                    closeOnEscape={false}
                    title="Session Timeout Warning"
                >
                    <Text size="sm" mb="md">
                        Your session will expire in {Math.ceil(timeLeft / 1000)} seconds.
                    </Text>
                    <Progress
                        value={(timeLeft / WARNING_TIME) * 100}
                        mb="md"
                        color="blue"
                    />
                    <Group justify="flex-end" mt="md">
                        <Button 
                            variant="outline" 
                            color="red" 
                            onClick={() => {
                                debug('User clicked "Logout Now"');
                                logout();
                            }}
                            disabled={isRefreshing}
                        >
                            Logout Now
                        </Button>
                        <Button 
                            onClick={() => {
                                debug('User clicked "Stay Connected"');
                                extendSession();
                            }}
                            loading={isRefreshing}
                            disabled={isRefreshing}
                        >
                            Stay Connected
                        </Button>
                    </Group>
                </Modal>
            )}
            {children}
        </SessionContext.Provider>
    );
} 

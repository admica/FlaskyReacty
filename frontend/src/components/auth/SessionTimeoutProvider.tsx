// PATH: src/components/auth/SessionTimeoutProvider.tsx

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Modal, Button, Progress, Text } from '@mantine/core';
import apiService from '../../services/api';

interface SessionContextType {
    resetSession: () => void;
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

const SESSION_TIMEOUT = 15 * 60 * 1000; // 15 minutes
const WARNING_TIME = 60 * 1000; // 1 minute warning
const REFRESH_BEFORE = 2 * 60 * 1000; // Refresh 2 minutes before expiry

export const SessionTimeoutProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const navigate = useNavigate();
    const [showWarning, setShowWarning] = useState(false);
    const [timeLeft, setTimeLeft] = useState(WARNING_TIME);
    const [warningTimer, setWarningTimer] = useState<NodeJS.Timeout>();
    const [sessionTimer, setSessionTimer] = useState<NodeJS.Timeout>();
    const [refreshTimer, setRefreshTimer] = useState<NodeJS.Timeout>();

    const performTokenRefresh = async () => {
        try {
            await apiService.refreshToken();
            console.log('Token refreshed successfully');
            return true;
        } catch (error) {
            console.error('Failed to refresh token:', error);
            return false;
        }
    };

    const resetSession = async () => {
        if (warningTimer) clearInterval(warningTimer);
        if (sessionTimer) clearTimeout(sessionTimer);
        if (refreshTimer) clearTimeout(refreshTimer);

        // Set up token refresh before expiry
        const newRefreshTimer = setTimeout(() => {
            performTokenRefresh().then(success => {
                if (success) {
                    resetSession(); // Reset timers after successful refresh
                }
            });
        }, SESSION_TIMEOUT - REFRESH_BEFORE);

        // Set up session warning
        const newSessionTimer = setTimeout(() => {
            setShowWarning(true);
            const newWarningTimer = setInterval(() => {
                setTimeLeft((prev) => {
                    if (prev <= 1000) {
                        logout();
                        return 0;
                    }
                    return prev - 1000;
                });
            }, 1000);
            setWarningTimer(newWarningTimer);
        }, SESSION_TIMEOUT - WARNING_TIME);

        setRefreshTimer(newRefreshTimer);
        setSessionTimer(newSessionTimer);
        setTimeLeft(WARNING_TIME);
        setShowWarning(false);
    };

    const logout = () => {
        if (warningTimer) clearInterval(warningTimer);
        if (sessionTimer) clearTimeout(sessionTimer);
        if (refreshTimer) clearTimeout(refreshTimer);
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        navigate('/login');
    };

    const extendSession = async () => {
        const success = await performTokenRefresh();
        if (success) {
            resetSession();
        } else {
            logout();
        }
    };

    useEffect(() => {
        const token = localStorage.getItem('token');
        if (token) {
            resetSession();
        }

        const events = ['mousedown', 'keydown', 'scroll', 'mousemove'];
        const resetOnActivity = () => {
            const token = localStorage.getItem('token');
            if (token && !showWarning) {
                resetSession();
            }
        };

        events.forEach(event => {
            window.addEventListener(event, resetOnActivity);
        });

        return () => {
            if (warningTimer) clearInterval(warningTimer);
            if (sessionTimer) clearTimeout(sessionTimer);
            if (refreshTimer) clearTimeout(refreshTimer);
            events.forEach(event => {
                window.removeEventListener(event, resetOnActivity);
            });
        };
    }, []);

    return (
        <SessionContext.Provider value={{ resetSession, logout }}>
            {children}
            <Modal
                opened={showWarning}
                onClose={() => {}}
                title="Session Timeout Warning"
                closeOnClickOutside={false}
                closeOnEscape={false}
                withCloseButton={false}
            >
                <Text size="sm" mb="md">
                    Your session will expire in {Math.ceil(timeLeft / 1000)} seconds.
                </Text>
                <Progress
                    value={(timeLeft / WARNING_TIME) * 100}
                    mb="md"
                    color="blue"
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                    <Button variant="outline" color="red" onClick={logout} fullWidth>
                        Logout Now
                    </Button>
                    <Button onClick={extendSession} fullWidth>
                        Stay Connected
                    </Button>
                </div>
            </Modal>
        </SessionContext.Provider>
    );
}; 
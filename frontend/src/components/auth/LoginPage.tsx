// PATH: src/components/auth/LoginPage.tsx
import { useState, useEffect, Suspense, lazy } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    TextInput,
    PasswordInput,
    Button,
    Paper,
    Title,
    Container,
    Alert,
    LoadingOverlay,
    rem,
} from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import apiService from '../../services/api';

// Lazy load the globe component
const BgGlobe = lazy(() => import('./bg'));

export function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    // Load remembered username on mount
    useEffect(() => {
        const remembered = localStorage.getItem('lastUsername');
        if (remembered) {
            setUsername(remembered);
        }
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const response = await apiService.login(username, password);
            localStorage.setItem('token', response.access_token);
            localStorage.setItem('username', username);
            localStorage.setItem('isAdmin', (response.role === 'admin').toString());
            navigate('/dashboard');
        } catch (err: any) {
            setError(err.error || 'Login failed. Please check your credentials.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            position: 'relative',
            width: '100vw',
            height: '100vh',
            overflow: 'hidden',
            background: '#1A1B1E',
            margin: 0,
            padding: 0
        }}>
            <Suspense fallback={null}>
                <BgGlobe />
            </Suspense>

            <Container
                size={420}
                style={{
                    position: 'relative',
                    zIndex: 1,
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    padding: '0 20px'
                }}
            >
                <Title
                    ta="center"
                    style={{
                        color: '#4facfe',
                        marginBottom: rem(40),
                        textShadow: '0 0 10px rgba(79, 172, 254, 0.5)',
                        fontSize: rem(40),
                        fontWeight: 700
                    }}
                >
                    AutoPCAP
                </Title>

                <Paper
                    withBorder
                    shadow="md"
                    p={rem(30)}
                    radius="md"
                    style={{
                        backgroundColor: 'rgba(26, 27, 30, 0.85)',
                        backdropFilter: 'blur(10px)',
                        border: '1px solid rgba(79, 172, 254, 0.2)',
                        maxWidth: '100%'
                    }}
                >
                    <LoadingOverlay visible={loading} overlayProps={{ blur: 2 }} />
                    <form onSubmit={handleSubmit}>
                        <TextInput
                            label="Username"
                            placeholder="Your username"
                            required
                            value={username}
                            onChange={(event: React.ChangeEvent<HTMLInputElement>) => setUsername(event.target.value)}
                            disabled={loading}
                            variant="filled"
                            styles={{
                                label: { 
                                    color: '#fff',
                                    marginBottom: rem(4)
                                },
                                input: {
                                    backgroundColor: 'rgba(0, 0, 0, 0.3)',
                                    borderColor: 'rgba(79, 172, 254, 0.2)',
                                    color: '#fff'
                                }
                            }}
                            classNames={{
                                input: 'focus:border-[#4facfe]'
                            }}
                        />

                        <PasswordInput
                            label="Password"
                            placeholder="Your password"
                            required
                            mt="md"
                            value={password}
                            onChange={(event: React.ChangeEvent<HTMLInputElement>) => setPassword(event.target.value)}
                            disabled={loading}
                            variant="filled"
                            styles={{
                                label: { 
                                    color: '#fff',
                                    marginBottom: rem(4)
                                },
                                input: {
                                    backgroundColor: 'rgba(0, 0, 0, 0.3)',
                                    borderColor: 'rgba(79, 172, 254, 0.2)',
                                    color: '#fff'
                                },
                                innerInput: {
                                    color: '#fff'
                                }
                            }}
                            classNames={{
                                input: 'focus:border-[#4facfe]'
                            }}
                        />

                        {error && (
                            <Alert
                                icon={<IconAlertCircle size={16} />}
                                title="Error"
                                color="red"
                                mt="md"
                                variant="filled"
                                styles={{
                                    root: {
                                        backgroundColor: 'rgba(225, 45, 57, 0.15)',
                                    },
                                    title: {
                                        color: '#ff4b4b'
                                    },
                                    message: {
                                        color: '#fff'
                                    }
                                }}
                            >
                                {error}
                            </Alert>
                        )}

                        <Button
                            fullWidth
                            mt="xl"
                            type="submit"
                            loading={loading}
                            variant="gradient"
                            gradient={{ from: '#4facfe', to: '#00f2fe', deg: 45 }}
                            styles={{
                                root: {
                                    height: rem(42)
                                }
                            }}
                        >
                            {loading ? 'Signing in...' : 'Sign in'}
                        </Button>
                    </form>
                </Paper>
            </Container>
        </div>
    );
}

export default LoginPage; 
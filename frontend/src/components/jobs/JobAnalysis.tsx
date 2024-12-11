// PATH: src/components/jobs/JobAnalysis.tsx

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Paper,
    Title,
    LoadingOverlay,
    Alert,
    Group,
    Button,
    Grid,
    Image,
    Text,
    Stack,
    Card,
} from '@mantine/core';
import { IconAlertCircle, IconArrowLeft } from '@tabler/icons-react';
import apiService from '../../services/api';

interface AnalysisData {
    protocol_distribution: {
        data: Record<string, number>;
        image_url: string;
    };
    conversation_matrix: {
        data: any;
        image_url: string;
    };
    bandwidth_usage: {
        data: any;
        image_url: string;
    };
    packet_size_distribution: {
        data: any;
        image_url: string;
    };
}

export function JobAnalysis() {
    const { jobId } = useParams<{ jobId: string }>();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [analysis, setAnalysis] = useState<AnalysisData | null>(null);

    useEffect(() => {
        loadAnalysis();
    }, [jobId]);

    const loadAnalysis = async () => {
        if (!jobId) return;
        
        try {
            setLoading(true);
            const data = await apiService.getJobAnalysis(parseInt(jobId));
            setAnalysis(data);
            setError(null);
        } catch (err: any) {
            setError(err.error || 'Failed to load analysis');
            console.error('Error loading analysis:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleBack = () => {
        navigate('/jobs');
    };

    if (!jobId) {
        return <Alert color="red">Invalid job ID</Alert>;
    }

    return (
        <div style={{ position: 'relative' }}>
            <LoadingOverlay visible={loading} />

            <Group justify="space-between" mb="md">
                <Group>
                    <Button
                        variant="subtle"
                        leftSection={<IconArrowLeft size={16} />}
                        onClick={handleBack}
                    >
                        Back to Jobs
                    </Button>
                    <Title order={2}>Job Analysis - #{jobId}</Title>
                </Group>
            </Group>

            {error && (
                <Alert 
                    icon={<IconAlertCircle size={16} />}
                    color="red"
                    mb="md"
                    title="Error"
                    variant="light"
                >
                    {error}
                </Alert>
            )}

            {analysis && (
                <Grid>
                    {/* Protocol Distribution */}
                    <Grid.Col span={6}>
                        <Paper withBorder p="md">
                            <Stack>
                                <Title order={3}>Protocol Distribution</Title>
                                {analysis.protocol_distribution.image_url && (
                                    <Image
                                        src={analysis.protocol_distribution.image_url}
                                        alt="Protocol Distribution"
                                    />
                                )}
                                {analysis.protocol_distribution.data && (
                                    <Card withBorder>
                                        <Stack gap="xs">
                                            {Object.entries(analysis.protocol_distribution.data)
                                                .sort(([, a], [, b]) => b - a)
                                                .map(([protocol, count]) => (
                                                    <Group key={protocol} justify="space-between">
                                                        <Text>{protocol}</Text>
                                                        <Text fw={500}>{count.toLocaleString()}</Text>
                                                    </Group>
                                                ))
                                            }
                                        </Stack>
                                    </Card>
                                )}
                            </Stack>
                        </Paper>
                    </Grid.Col>

                    {/* Conversation Matrix */}
                    <Grid.Col span={6}>
                        <Paper withBorder p="md">
                            <Stack>
                                <Title order={3}>Conversation Matrix</Title>
                                {analysis.conversation_matrix.image_url && (
                                    <Image
                                        src={analysis.conversation_matrix.image_url}
                                        alt="Conversation Matrix"
                                    />
                                )}
                            </Stack>
                        </Paper>
                    </Grid.Col>

                    {/* Bandwidth Usage */}
                    <Grid.Col span={6}>
                        <Paper withBorder p="md">
                            <Stack>
                                <Title order={3}>Bandwidth Usage</Title>
                                {analysis.bandwidth_usage.image_url && (
                                    <Image
                                        src={analysis.bandwidth_usage.image_url}
                                        alt="Bandwidth Usage"
                                    />
                                )}
                            </Stack>
                        </Paper>
                    </Grid.Col>

                    {/* Packet Size Distribution */}
                    <Grid.Col span={6}>
                        <Paper withBorder p="md">
                            <Stack>
                                <Title order={3}>Packet Size Distribution</Title>
                                {analysis.packet_size_distribution.image_url && (
                                    <Image
                                        src={analysis.packet_size_distribution.image_url}
                                        alt="Packet Size Distribution"
                                    />
                                )}
                            </Stack>
                        </Paper>
                    </Grid.Col>
                </Grid>
            )}
        </div>
    );
} 
import { useEffect, useState, useMemo } from 'react';
import { Table, Group, Text, Paper, Select, UnstyledButton, Center } from '@mantine/core';
import { IconChevronUp, IconChevronDown, IconSelector } from '@tabler/icons-react';
import api from '../../api/axios';

interface LocationCount {
  src_location: string;
  dst_location: string;
  count: number;
}

interface Location {
  site: string;
  name: string;
  latitude: number;
  longitude: number;
}

interface NetworkTableProps {
  sourceFilter: string | null;
  destFilter: string | null;
  onSourceFilterChange: (value: string | null) => void;
  onDestFilterChange: (value: string | null) => void;
}

type SortField = 'src_location' | 'dst_location' | 'count';
type SortDirection = 'asc' | 'desc' | null;

interface ThProps {
  children: React.ReactNode;
  reversed: boolean;
  sorted: boolean;
  onSort(): void;
}

function Th({ children, reversed, sorted, onSort }: ThProps) {
  const Icon = sorted
    ? reversed
      ? IconChevronUp
      : IconChevronDown
    : IconSelector;

  return (
    <Table.Th>
      <UnstyledButton onClick={onSort} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <span>{children}</span>
        <Center>
          <Icon size={14} stroke={1.5} />
        </Center>
      </UnstyledButton>
    </Table.Th>
  );
}

export function NetworkTable({ 
  sourceFilter, 
  destFilter, 
  onSourceFilterChange, 
  onDestFilterChange 
}: NetworkTableProps) {
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationCounts, setLocationCounts] = useState<LocationCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);

  // Load locations for filter dropdowns
  useEffect(() => {
    const loadLocations = async () => {
      try {
        const response = await api.get('/api/v1/network/locations');
        setLocations(response.data.locations);
      } catch (error) {
        console.error('Failed to load locations:', error);
      }
    };
    loadLocations();
  }, []);

  // Load location counts with filters
  useEffect(() => {
    const loadLocationCounts = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (sourceFilter) params.append('src', sourceFilter);
        if (destFilter) params.append('dst', destFilter);
        
        const response = await api.get(`/api/v1/subnet-location-counts?${params.toString()}`);
        setLocationCounts(response.data);
      } catch (error) {
        console.error('Failed to load location counts:', error);
      } finally {
        setLoading(false);
      }
    };
    loadLocationCounts();
  }, [sourceFilter, destFilter]);

  // Create location options for dropdowns based on active data
  const locationOptions = useMemo(() => {
    // Get unique source locations from current data
    const activeSources = new Set(locationCounts.map(count => count.src_location));
    const activeDestinations = new Set(locationCounts.map(count => count.dst_location));

    // Create source options
    const sourceOptions = Array.from(activeSources).map(site => {
      const location = locations.find(loc => loc.site === site);
      return {
        value: site,
        label: location ? `${site} - ${location.name}` : site
      };
    }).sort((a, b) => a.value.localeCompare(b.value));

    // Create destination options
    const destOptions = Array.from(activeDestinations).map(site => {
      const location = locations.find(loc => loc.site === site);
      return {
        value: site,
        label: location ? `${site} - ${location.name}` : site
      };
    }).sort((a, b) => a.value.localeCompare(b.value));

    return {
      sources: sourceOptions,
      destinations: destOptions
    };
  }, [locationCounts, locations]);

  // Sort the data
  const sortedData = useMemo(() => {
    if (!sortField || !sortDirection) return locationCounts;

    return [...locationCounts].sort((a, b) => {
      const modifier = sortDirection === 'asc' ? 1 : -1;
      
      if (sortField === 'count') {
        return (a[sortField] - b[sortField]) * modifier;
      }
      
      return a[sortField].localeCompare(b[sortField]) * modifier;
    });
  }, [locationCounts, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((current) => {
        if (current === 'asc') return 'desc';
        if (current === 'desc') return null;
        return 'asc';
      });
    } else {
      setSortField(field);
      setSortDirection('asc');
    }

    if (sortField !== field) {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  return (
    <Paper p="md">
      <Group mb="md">
        <Select
          label="Source Location"
          placeholder="All Sources"
          data={locationOptions.sources}
          value={sourceFilter}
          onChange={onSourceFilterChange}
          clearable
          searchable
          style={{ width: 250 }}
        />
        <Select
          label="Destination Location"
          placeholder="All Destinations"
          data={locationOptions.destinations}
          value={destFilter}
          onChange={onDestFilterChange}
          clearable
          searchable
          style={{ width: 250 }}
        />
      </Group>

      <Table>
        <Table.Thead>
          <Table.Tr>
            <Th
              sorted={sortField === 'src_location'}
              reversed={sortDirection === 'desc'}
              onSort={() => handleSort('src_location')}
            >
              Source
            </Th>
            <Th
              sorted={sortField === 'dst_location'}
              reversed={sortDirection === 'desc'}
              onSort={() => handleSort('dst_location')}
            >
              Destination
            </Th>
            <Th
              sorted={sortField === 'count'}
              reversed={sortDirection === 'desc'}
              onSort={() => handleSort('count')}
            >
              Count
            </Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {loading ? (
            <Table.Tr>
              <Table.Td colSpan={3}>
                <Text ta="center">Loading...</Text>
              </Table.Td>
            </Table.Tr>
          ) : sortedData.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={3}>
                <Text ta="center">No data found</Text>
              </Table.Td>
            </Table.Tr>
          ) : (
            sortedData.map((count, index) => (
              <Table.Tr key={index}>
                <Table.Td>{count.src_location}</Table.Td>
                <Table.Td>{count.dst_location}</Table.Td>
                <Table.Td>{count.count.toLocaleString()}</Table.Td>
              </Table.Tr>
            ))
          )}
        </Table.Tbody>
      </Table>
    </Paper>
  );
} 
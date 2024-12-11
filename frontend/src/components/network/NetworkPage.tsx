// PATH: src/components/network/NetworkPage.tsx

import { Box } from '@mantine/core';
import { Tabs } from '@mantine/core';
import { NetworkGlobe } from './NetworkGlobe';
import { NetworkTable } from './NetworkTable';
import { useState } from 'react';

export function NetworkPage() {
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [destFilter, setDestFilter] = useState<string | null>(null);

  const handleTabChange = (value: string | null) => {
    console.log(`Tab changed to: ${value}`);
  };

  return (
    <Box style={{ 
      height: 'calc(100vh - 60px)', // Account for main nav
      display: 'flex',
      flexDirection: 'column'
    }}>
      <Tabs defaultValue="globe" onChange={handleTabChange} style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Tabs.List>
          <Tabs.Tab value="globe">Globe View</Tabs.Tab>
          <Tabs.Tab value="table">Table View</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="globe" pt="xs" style={{ flex: 1 }}>
          <NetworkGlobe 
            sourceFilter={sourceFilter}
            destFilter={destFilter}
          />
        </Tabs.Panel>

        <Tabs.Panel value="table" pt="xs" style={{ flex: 1 }}>
          <NetworkTable 
            sourceFilter={sourceFilter}
            destFilter={destFilter}
            onSourceFilterChange={setSourceFilter}
            onDestFilterChange={setDestFilter}
          />
        </Tabs.Panel>
      </Tabs>
    </Box>
  );
} 
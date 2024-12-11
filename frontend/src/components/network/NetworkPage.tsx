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
    <Box p="md">
      <Tabs defaultValue="globe" onChange={handleTabChange}>
        <Tabs.List>
          <Tabs.Tab value="globe">Globe View</Tabs.Tab>
          <Tabs.Tab value="table">Table View</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="globe" pt="xs">
          <NetworkGlobe 
            sourceFilter={sourceFilter}
            destFilter={destFilter}
          />
        </Tabs.Panel>

        <Tabs.Panel value="table" pt="xs">
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
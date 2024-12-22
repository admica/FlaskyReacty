// PATH: src/components/network/NetworkGlobe.tsx
// Globe images originally from: https://visibleearth.nasa.gov/
import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import Globe from 'react-globe.gl';
import apiService from '../../services/api';
import { Slider, Text, Paper, Title, Stack, Group, ActionIcon, ScrollArea } from '@mantine/core';
import type { Location, ApiConnection } from '../../services/api';

interface GlobePoint {
  lat: number;
  lng: number;
  name: string;
  radius: number;
  site: string;
  color: string;
  description?: string;
  altitude: number;
  connections?: {
    incoming: Array<{ from: string; packets: number }>;
    outgoing: Array<{ to: string; packets: number }>;
  };
}

interface NetworkConnection {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  color: string;
  tooltipContent: string;
  details: {
    src_location: string;
    dst_location: string;
    packet_count: number;
    earliest_seen: number;
    latest_seen: number;
  };
}

interface DebugMessage {
  id: number;
  timestamp: Date;
  message: string;
}

interface DetailsData {
  type: 'location' | 'connection';
  data: GlobePoint | NetworkConnection['details'];
}

function formatPacketCount(count: number): string {
  const addCommas = (num: string) => num.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  
  if (count >= 1000000000000) {
    const num = (count / 1000000000000).toFixed(1);
    return `${addCommas(num)}T`;
  }
  if (count >= 1000000000) {
    const num = (count / 1000000000).toFixed(1);
    return `${addCommas(num)}B`;
  }
  if (count >= 1000000) {
    const num = (count / 1000000).toFixed(1);
    return `${addCommas(num)}M`;
  }
  if (count >= 1000) {
    const num = (count / 1000).toFixed(1);
    return `${addCommas(num)}K`;
  }
  return addCommas(count.toString());
}

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString();
}

interface NetworkGlobeProps {
  sourceFilter: string | null;
  destFilter: string | null;
}

export function NetworkGlobe({ sourceFilter, destFilter }: NetworkGlobeProps) {
  const globeEl = useRef<any>();
  const [locations, setLocations] = useState<GlobePoint[]>([]);
  const [connections, setConnections] = useState<NetworkConnection[]>([]);
  const [rotationSpeed, setRotationSpeed] = useState(0.3);
  const [zoomLevel, setZoomLevel] = useState(1.1);
  const [debugMessages, setDebugMessages] = useState<DebugMessage[]>([]);
  const [selectedDetails, setSelectedDetails] = useState<DetailsData | null>(null);
  const messageIdCounter = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ width: window.innerWidth, height: window.innerHeight - 120 });
  const dataLoaded = useRef(false);
  const [arcHeight] = useState<number>(.1);
  const [showDebug, setShowDebug] = useState(false);
  const wasRotatingRef = useRef(true);
  const previousRotationSpeedRef = useRef(0.5);
  const resizeTimeoutRef = useRef<NodeJS.Timeout>();

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) {
      console.log('Container ref not initialized');
      return;
    }

    const updateSize = () => {
      if (containerRef.current) {
        const { clientWidth, clientHeight } = containerRef.current;
        // Only update if size actually changed to prevent unnecessary re-renders
        setContainerSize(prev => {
          if (prev.width === clientWidth && prev.height === clientHeight) {
            return prev;
          }
          console.log('Container size updated:', { width: clientWidth, height: clientHeight });
          return { width: clientWidth, height: clientHeight };
        });
      }
    };

    // Debounced resize handler to prevent rapid updates
    const debouncedResize = () => {
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current);
      }
      resizeTimeoutRef.current = setTimeout(updateSize, 100);
    };

    const resizeObserver = new ResizeObserver(debouncedResize);
    resizeObserver.observe(containerRef.current);
    
    // Initial size update
    updateSize();

    return () => {
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current);
      }
      resizeObserver.disconnect();
    };
  }, []);

  // Debug logging function
  const addDebugMessage = useCallback((message: string) => {
    const newMessage = {
      id: messageIdCounter.current++,
      timestamp: new Date(),
      message
    };
    setDebugMessages(prev => [...prev.slice(-999), newMessage]);
  }, []);

  // Get current month's globe texture
  const globeTexture = useMemo(() => {
    const currentMonth = new Date().getMonth() + 1;
    const texturePath = `/globe${currentMonth}.png`;
    console.log('Loading globe texture:', texturePath);
    return texturePath;
  }, []);

  // Handle hover states
  const handleHoverStart = useCallback((obj: any) => {
    if (!globeEl.current) return;
    const controls = globeEl.current.controls();

    if (obj) {
      // Only stop rotation if we're currently rotating
      if (controls.autoRotate) {
        wasRotatingRef.current = true;
        previousRotationSpeedRef.current = controls.autoRotateSpeed;
        controls.autoRotate = false;
      }

      // Show location details if it's a point
      if (obj.name) { // Points have a name property
        const globePoint = obj as GlobePoint;
        const incomingConnections = connections.filter(
          conn => conn.details.dst_location === globePoint.site
        );
        const outgoingConnections = connections.filter(
          conn => conn.details.src_location === globePoint.site
        );

        setSelectedDetails({
          type: 'location',
          data: {
            ...globePoint,
            connections: {
              incoming: incomingConnections.map(conn => ({
                from: conn.details.src_location,
                packets: conn.details.packet_count
              })),
              outgoing: outgoingConnections.map(conn => ({
                to: conn.details.dst_location,
                packets: conn.details.packet_count
              }))
            }
          } as GlobePoint
        });
      }
      // Show connection details if it's an arc
      else if (obj.startLat !== undefined) { // Arcs have startLat/startLng properties
        const connection = obj as NetworkConnection;
        setSelectedDetails({
          type: 'connection',
          data: connection.details
        });
      }
    } else {
      // Null event means hover end - only restore rotation
      if (wasRotatingRef.current) {
        controls.autoRotate = true;
        controls.autoRotateSpeed = previousRotationSpeedRef.current;
        wasRotatingRef.current = false;
      }
      // Don't clear details on hover end
    }
  }, [connections]);

  // Initialize globe
  useEffect(() => {
    if (!globeEl.current) {
      console.log('Globe element not initialized yet');
      return;
    }
    
    console.log('Initializing globe with texture:', globeTexture);
    const controls = globeEl.current.controls();
    controls.autoRotate = true;
    controls.autoRotateSpeed = rotationSpeed;
    controls.enableZoom = true;
    controls.enablePan = true;
    controls.enableRotate = true;
    controls.minDistance = 120;
    globeEl.current.pointOfView({ lat: 36.5, lng: -86, altitude: zoomLevel });

    // Store initial rotation state
    wasRotatingRef.current = true;
    previousRotationSpeedRef.current = rotationSpeed;
  }, [rotationSpeed, globeTexture, zoomLevel]);

  // Handle zoom level changes
  useEffect(() => {
    if (!globeEl.current) return;
    const currentView = globeEl.current.pointOfView();
    globeEl.current.pointOfView({
      lat: currentView.lat,
      lng: currentView.lng,
      altitude: zoomLevel
    });
  }, [zoomLevel]);

  // Process connections data
  const processConnections = useCallback((apiConnections: ApiConnection[], locations: Location[]) => {
    // Create a lookup map for locations
    const locationMap = new Map(locations.map(loc => [loc.site, { lat: loc.latitude, lng: loc.longitude }]));
    addDebugMessage(`Location map has ${locationMap.size} entries`);
    
    const processed = apiConnections
      .map((conn) => {
        addDebugMessage(`Processing connection: ${conn.src_location} → ${conn.dst_location}`);
        
        // Case-insensitive lookup
        const srcLocation = locations.find(loc => 
          loc.site.toLowerCase() === conn.src_location.toLowerCase()
        );
        const dstLocation = locations.find(loc => 
          loc.site.toLowerCase() === conn.dst_location.toLowerCase()
        );
        
        if (!srcLocation || !dstLocation) {
          addDebugMessage(`Missing coordinates for ${conn.src_location} → ${conn.dst_location}`);
          if (!srcLocation) addDebugMessage(`Missing source location: ${conn.src_location}`);
          if (!dstLocation) addDebugMessage(`Missing destination location: ${conn.dst_location}`);
          return null;
        }

        return {
          startLat: srcLocation.latitude,
          startLng: srcLocation.longitude,
          endLat: dstLocation.latitude,
          endLng: dstLocation.longitude,
          color: 'rgba(255, 255, 555, 0.5)',
          tooltipContent: `${srcLocation.site} → ${dstLocation.site}
Packets: ${formatPacketCount(conn.packet_count)}
First Seen: ${formatTimestamp(conn.earliest_seen)}
Last Seen: ${formatTimestamp(conn.latest_seen)}`,
          details: {
            src_location: srcLocation.site,
            dst_location: dstLocation.site,
            packet_count: conn.packet_count,
            earliest_seen: conn.earliest_seen,
            latest_seen: conn.latest_seen
          }
        };
      })
      .filter((conn): conn is NetworkConnection => conn !== null);
    
    addDebugMessage(`Processed ${processed.length} valid connections out of ${apiConnections.length} total`);
    return processed;
  }, [addDebugMessage]);

  // Load initial data
  useEffect(() => {
    const loadData = async () => {
      try {
        addDebugMessage('Loading locations and connections...');
        console.log('Loading locations and connections...');
        
        // Load locations first
        const locationsResponse = await apiService.getLocations();
        console.log('Locations response:', locationsResponse);
        addDebugMessage(`Loaded ${locationsResponse.locations.length} locations from API`);

        // Process locations
        const points: GlobePoint[] = locationsResponse.locations.map(loc => {
          console.log('Processing location:', loc);
          addDebugMessage(`Processing location: ${loc.site} (${loc.latitude}, ${loc.longitude}) color: ${loc.color}`);
          return {
            lat: loc.latitude,
            lng: loc.longitude,
            name: loc.name,
            site: loc.site,
            radius: 0.5,
            color: loc.color || '#FFFFFF',  // Use location color or default to white
            description: loc.description,
            altitude: loc.color === '#105BD8' ? 0.06 : 0.04  // NASA centers are taller
          };
        });
        console.log('Setting locations:', points);
        setLocations(points);
        addDebugMessage(`Processed ${points.length} locations`);

        // Load connections
        const connectionsResponse = await apiService.getConnections();
        console.log('Connections response:', connectionsResponse);
        addDebugMessage(`Loaded ${connectionsResponse.connections.length} connections from API`);

        // Process connections
        let processedConnections: NetworkConnection[] = [];
        if (connectionsResponse.connections) {
          processedConnections = processConnections(
            connectionsResponse.connections,
            locationsResponse.locations
          ) || [];
          console.log('Setting connections:', processedConnections);
          setConnections(processedConnections);
          addDebugMessage(`Processed ${processedConnections.length} connections`);
        }

        // Show JSC details initially
        const jscPoint = points.find(point => point.site === 'JSC');
        if (jscPoint) {
          const incomingConnections = processedConnections.filter(
            conn => conn.details.dst_location === jscPoint.site
          );
          const outgoingConnections = processedConnections.filter(
            conn => conn.details.src_location === jscPoint.site
          );

          setSelectedDetails({
            type: 'location',
            data: {
              ...jscPoint,
              connections: {
                incoming: incomingConnections.map(conn => ({
                  from: conn.details.src_location,
                  packets: conn.details.packet_count
                })),
                outgoing: outgoingConnections.map(conn => ({
                  to: conn.details.dst_location,
                  packets: conn.details.packet_count
                }))
              }
            } as GlobePoint
          });
        }

        dataLoaded.current = true;
      } catch (error: any) {
        const errorMessage = error.response?.data?.error || error.response?.data || error.message || 'Unknown error';
        console.error('Error loading globe data:', error);
        addDebugMessage(`Error loading data: ${errorMessage}`);
      }
    };

    if (!dataLoaded.current) {
      loadData();
    }
  }, [processConnections, addDebugMessage]);

  // Handle clicks
  const handleLocationClick = useCallback((point: object, _event: MouseEvent, _coords: { lat: number, lng: number, altitude: number }) => {
    const globePoint = point as GlobePoint;
    if (!globePoint) return;

    const incomingConnections = connections.filter(
      conn => conn.details.dst_location === globePoint.site
    );
    const outgoingConnections = connections.filter(
      conn => conn.details.src_location === globePoint.site
    );

    setSelectedDetails({
      type: 'location',
      data: {
        ...globePoint,
        connections: {
          incoming: incomingConnections.map(conn => ({
            from: conn.details.src_location,
            packets: conn.details.packet_count
          })),
          outgoing: outgoingConnections.map(conn => ({
            to: conn.details.dst_location,
            packets: conn.details.packet_count
          }))
        }
      } as GlobePoint
    });
  }, [connections]);

  const handleConnectionClick = useCallback((arc: object, _event: MouseEvent, _coords: { lat: number, lng: number, altitude: number }) => {
    const connection = arc as NetworkConnection;
    if (!connection) return;
    setSelectedDetails({
      type: 'connection',
      data: connection.details
    });
  }, []);

  // Filter connections based on source/dest filters
  const filteredConnections = useMemo(() => {
    if (!sourceFilter && !destFilter) return connections;
    
    return connections.filter(conn => {
      const matchesSource = !sourceFilter || conn.details.src_location.toLowerCase() === sourceFilter.toLowerCase();
      const matchesDest = !destFilter || conn.details.dst_location.toLowerCase() === destFilter.toLowerCase();
      return matchesSource && matchesDest;
    });
  }, [connections, sourceFilter, destFilter]);

  // Filter locations to only show those that are part of filtered connections
  const filteredLocations = useMemo(() => {
    if (!sourceFilter && !destFilter) return locations;

    const activeLocations = new Set<string>();
    filteredConnections.forEach(conn => {
      activeLocations.add(conn.details.src_location.toLowerCase());
      activeLocations.add(conn.details.dst_location.toLowerCase());
    });

    return locations.filter(loc => 
      activeLocations.has(loc.site.toLowerCase())
    );
  }, [locations, filteredConnections, sourceFilter, destFilter]);

  return (
    <div ref={containerRef} style={{
      width: '100%',
      height: 'calc(100vh - 120px)',
      position: 'relative',
      backgroundColor: '#000000',
      overflow: 'hidden'  // Prevent scrollbars during size changes
    }}>
      {/* Loading indicator */}
      {(!dataLoaded.current || locations.length === 0) && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 10,
          background: 'rgba(0, 0, 0, 0.7)',
          padding: '12px 15px',
          borderRadius: '4px'
        }}>
          <Text c="white">Loading globe data...</Text>
        </div>
      )}

      {/* Container size debug */}
      <div style={{
        position: 'absolute',
        top: 10,
        left: 10,
        zIndex: 10,
        background: 'rgba(0, 0, 0, 0.7)',
        padding: '4px 8px',
        borderRadius: '4px',
        color: 'white',
        fontSize: '12px'
      }}>
        Container: {containerSize.width}x{containerSize.height}
      </div>

      {/* Globe */}
      <Globe
        ref={globeEl}
        width={containerSize.width}
        height={containerSize.height}
        globeImageUrl={globeTexture}
        backgroundColor="rgba(0,0,0,0)"
        atmosphereColor="#4facfe"
        atmosphereAltitude={0.2}
        pointsData={filteredLocations}
        pointLat="lat"
        pointLng="lng"
        pointColor={(d: any) => d.color}
        pointAltitude="altitude"
        pointRadius="radius"
        pointResolution={24}
        pointsMerge={false}
        pointLabel={((d: any) => d.name) as any}
        labelColor={() => '#ffffff'}
        labelSize={1.5}
        labelDotRadius={0.5}
        labelAltitude={0.01}
        arcsData={filteredConnections}
        arcStartLat="startLat"
        arcStartLng="startLng"
        arcEndLat="endLat"
        arcEndLng="endLng"
        arcColor="color"
        arcDashLength={0.4}
        arcDashGap={0.2}
        arcDashAnimateTime={1500}
        arcStroke={1}
        arcLabel="tooltipContent"
        arcAltitude={arcHeight}
        onPointHover={handleHoverStart}
        onArcHover={handleHoverStart}
        onPointClick={handleLocationClick}
        onArcClick={handleConnectionClick}
        onGlobeReady={() => {
          addDebugMessage('Globe rendering complete');
          dataLoaded.current = true;
        }}
      />

      {/* Controls Overlay */}
      <Paper
        style={{
          position: 'absolute',
          top: 5,
          right: 5,
          zIndex: 10,
          background: 'rgba(0, 0, 0, 0.7)',
          padding: '12px 15px',
          width: 'auto',
          minWidth: '250px'
        }}
      >
        <Text ta="center" size="sm" fw={500} c="white" mb={4}>
          Animation Speed: {rotationSpeed.toFixed(1)}
        </Text>
        <Slider
          value={rotationSpeed}
          onChange={(value) => {
            setRotationSpeed(value);
            if (globeEl.current) {
              const controls = globeEl.current.controls();
              controls.autoRotateSpeed = value;
            }
          }}
          min={0}
          max={3}
          step={0.1}
        />
      </Paper>

      {/* Zoom Control */}
      <Paper
        style={{
          position: 'absolute',
          top: 75,
          right: 5,
          zIndex: 10,
          background: 'rgba(0, 0, 0, 0.7)',
          padding: '12px 15px',
          width: 'auto',
          minWidth: '250px'
        }}
      >
        <Text ta="center" size="sm" fw={500} c="white" mb={4}>
          Zoom: {zoomLevel.toFixed(1)}
        </Text>
        <Slider
          value={zoomLevel}
          onChange={(value) => {
            setZoomLevel(value);
            if (globeEl.current) {
              const controls = globeEl.current.controls();
              controls.minDistance = 120;
              // Get current view position
              const currentView = globeEl.current.pointOfView();
              // Update only the altitude
              globeEl.current.pointOfView({ 
                lat: currentView.lat, 
                lng: currentView.lng, 
                altitude: value 
              });
            }
          }}
          min={0.4}
          max={3.0}
          step={0.1}
        />
      </Paper>

      {/* Details Panel */}
      {selectedDetails && (
        <Paper
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            zIndex: 10,
            background: 'rgba(0, 0, 0, 0.7)',
            padding: '12px 15px',
            width: '300px',
            maxHeight: 'calc(100% - 40px)',
            overflowY: 'auto'
          }}
        >
          <Stack gap="xs">
            <Title order={4} c="white" mb={2}>
              {selectedDetails.type === 'location' ? 'Location Details' : 'Connection Details'}
            </Title>
            
            {selectedDetails.type === 'location' && (
              <>
                <Text c="white" size="lg" fw={500} mb={1}>
                  {(selectedDetails.data as GlobePoint).site}
                </Text>
                <Text c="white" mb={4} size="sm">
                  {(selectedDetails.data as any).description}
                </Text>

                {(selectedDetails.data as any).connections.incoming.length > 0 && (
                  <>
                    <Text c="white" fw={500} mb={1} size="sm">Incoming Connections:</Text>
                    <div style={{ lineHeight: '1.1' }}>
                      {(selectedDetails.data as any).connections.incoming.map((conn: any, i: number) => (
                        <Text key={i} c="dimmed" size="xs" mb={0}>
                          From {conn.from}: {formatPacketCount(conn.packets)} packets
                        </Text>
                      ))}
                    </div>
                  </>
                )}

                {(selectedDetails.data as any).connections.outgoing.length > 0 && (
                  <>
                    <Text c="white" fw={500} mt={4} mb={1} size="sm">Outgoing Connections:</Text>
                    <div style={{ lineHeight: '1.1' }}>
                      {(selectedDetails.data as any).connections.outgoing.map((conn: any, i: number) => (
                        <Text key={i} c="dimmed" size="xs" mb={0}>
                          To {conn.to}: {formatPacketCount(conn.packets)} packets
                        </Text>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}

            {selectedDetails.type === 'connection' && (
              <>
                <Text c="white" mb={4}>
                  <strong>Source:</strong> {(selectedDetails.data as NetworkConnection['details']).src_location}
                </Text>
                <Text c="white" mb={4}>
                  <strong>Destination:</strong> {(selectedDetails.data as NetworkConnection['details']).dst_location}
                </Text>
                <Text c="white" mb={4}>
                  <strong>Packets:</strong> {formatPacketCount((selectedDetails.data as NetworkConnection['details']).packet_count)}
                </Text>
                <Text c="white" mb={4}>
                  <strong>First Seen:</strong> {formatTimestamp((selectedDetails.data as NetworkConnection['details']).earliest_seen)}
                </Text>
                <Text c="white" mb={4}>
                  <strong>Last Seen:</strong> {formatTimestamp((selectedDetails.data as NetworkConnection['details']).latest_seen)}
                </Text>
              </>
            )}

            <Text 
              c="dimmed" 
              size="sm" 
              style={{ cursor: 'pointer' }}
              onClick={() => setSelectedDetails(null)}
              mt={8}
            >
              Click to close
            </Text>
          </Stack>
        </Paper>
      )}

      {/* Debug Messages Overlay */}
      <Paper
        style={{
          position: 'absolute',
          bottom: 10,
          right: 10,
          zIndex: 10,
          background: 'rgba(0, 0, 0, 0.8)',
          backdropFilter: 'blur(4px)',
          padding: '8px 12px',
          width: '440px',
          maxHeight: '300px',
          display: showDebug ? 'block' : 'none'
        }}
      >
        <Stack gap="xs">
          <Group justify="space-between">
            <Text size="xs" fw={500} c="dimmed">
              Debug Log ({debugMessages.length} messages) - Globe Status: {dataLoaded.current ? 'Loaded' : 'Loading'}
            </Text>
            <Group gap="xs">
              <Text size="xs" c="dimmed">{new Date().toLocaleTimeString()}</Text>
              <ActionIcon 
                size="xs" 
                variant="subtle" 
                color="gray" 
                onClick={() => setShowDebug(false)}
              >
                ×
              </ActionIcon>
            </Group>
          </Group>
          <ScrollArea h={250} scrollbarSize={8}>
            <Stack gap={4}>
              {debugMessages.map(msg => (
                <Text 
                  key={msg.id} 
                  size="xs" 
                  c="dimmed" 
                  style={{ 
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    lineHeight: 1.2,
                    userSelect: 'text'
                  }}
                >
                  <Text span c="dimmed" size="xs" style={{ userSelect: 'text' }}>
                    [{msg.timestamp.toLocaleTimeString()}]
                  </Text>{' '}
                  {msg.message}
                </Text>
              ))}
            </Stack>
          </ScrollArea>
        </Stack>
      </Paper>

      {/* Debug Trigger Area */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          right: 0,
          width: '100px',
          height: '100px',
          zIndex: 9
        }}
        onMouseEnter={() => setShowDebug(true)}
      />
    </div>
  );
} 


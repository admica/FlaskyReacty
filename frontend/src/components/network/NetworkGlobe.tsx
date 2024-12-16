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
  const [containerSize, setContainerSize] = useState({ width: window.innerWidth, height: window.innerHeight - 60 });
  const dataLoaded = useRef(false);
  const [arcHeight] = useState<number>(.1);
  const [showDebug, setShowDebug] = useState(false);
  const wasRotatingRef = useRef(true);
  const previousRotationSpeedRef = useRef(0.5);
  const resizeTimeoutRef = useRef<NodeJS.Timeout>();

  // Debounced resize observer
  useEffect(() => {
    if (!containerRef.current) return;

    const updateSize = () => {
      if (containerRef.current) {
        const { clientWidth, clientHeight } = containerRef.current;
        // Only update if size actually changed
        setContainerSize(prev => {
          if (prev.width === clientWidth && prev.height === clientHeight) {
            return prev;
          }
          return { width: clientWidth, height: clientHeight };
        });
      }
    };

    const debouncedResize = () => {
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current);
      }
      resizeTimeoutRef.current = setTimeout(updateSize, 100);
    };

    const resizeObserver = new ResizeObserver(debouncedResize);
    resizeObserver.observe(containerRef.current);
    updateSize(); // Initial size

    return () => {
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current);
      }
      resizeObserver.disconnect();
    };
  }, []);

  // Initialize globe with memoized config
  const globeConfig = useMemo(() => ({
    globeImageUrl: globeTexture,
    backgroundColor: 'rgba(0,0,0,0)',
    pointColor: 'color',
    pointAltitude: 'altitude',
    pointRadius: 'radius',
    pointLabel: 'name',
    arcColor: 'color',
    arcAltitude: arcHeight,
    arcStroke: 0.5,
    arcDashLength: 1,
    arcDashGap: 0,
    arcDashInitialGap: 0,
    arcDashAnimateTime: 2000,
    arcsTransitionDuration: 0,
    pointsTransitionDuration: 0,
    waitForGlobeReady: true,
  }), [arcHeight, globeTexture]);

  // Initialize globe once
  useEffect(() => {
    if (!globeEl.current) return;
    
    const controls = globeEl.current.controls();
    controls.autoRotate = true;
    controls.autoRotateSpeed = rotationSpeed;
    controls.enableZoom = true;
    controls.enablePan = true;
    controls.enableRotate = true;
    controls.minDistance = 120;
    
    globeEl.current.pointOfView({ lat: 36.5, lng: -86, altitude: zoomLevel }, 0);
    
    wasRotatingRef.current = true;
    previousRotationSpeedRef.current = rotationSpeed;
  }, []); // Empty dependency array - only run once

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
    <div 
      ref={containerRef} 
      style={{ 
        width: '100%', 
        height: '100%',
        position: 'absolute',
        top: 0,
        left: 0,
        overflow: 'hidden'
      }}
    >
      <Globe
        ref={globeEl}
        width={containerSize.width}
        height={containerSize.height}
        {...globeConfig}
        pointsData={locations}
        arcsData={connections}
        onObjectHover={handleHoverStart}
      />
      {/* ... rest of the JSX ... */}
    </div>
  );
} 

// PATH: src/components/auth/bg.tsx
import { useEffect, useRef, useState } from 'react';
import Globe from 'react-globe.gl';

interface NASALocation {
  id: string;
  name: string;
  lat: number;
  lng: number;
}

interface Connection {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  bandwidth: number;
  source: string;
  target: string;
  isInternational?: boolean;
}

const BgGlobe = () => {
  const globeEl = useRef<any>();
  const [arcs, setArcs] = useState<Connection[]>([]);

  // Get current month's globe image
  const currentMonth = new Date().getMonth() + 1; // getMonth() returns 0-11
  const globeImage = `/globe${currentMonth}.png`;

  // NASA locations
  const locations: NASALocation[] = [
    { id: 'HQ', name: 'HQ', lat: 38.9072, lng: -77.0365 },
    { id: 'JSC', name: 'JSC', lat: 29.7604, lng: -95.3698 },
    { id: 'KSC', name: 'KSC', lat: 28.4059, lng: -80.6081 },
    { id: 'MSFC', name: 'MSFC', lat: 34.7291, lng: -86.5861 },
    { id: 'GSFC', name: 'GSFC', lat: 38.9967, lng: -76.8484 },
    { id: 'ARC', name: 'ARC', lat: 37.4130, lng: -122.0644 },
  ];

  useEffect(() => {
    // Generate connections between NASA centers
    const connections: Connection[] = [];
    for (let i = 0; i < locations.length; i++) {
      for (let j = i + 1; j < locations.length; j++) {
        const source = locations[i];
        const target = locations[j];
        connections.push({
          startLat: source.lat,
          startLng: source.lng,
          endLat: target.lat,
          endLng: target.lng,
          bandwidth: 1000,
          source: source.id,
          target: target.id,
        });
      }
    }

    // Add international connections from JSC and ARC
    const jsc = locations.find(loc => loc.id === 'JSC')!;
    const arc = locations.find(loc => loc.id === 'ARC')!;

    const internationalConnections = [
      // JSC connections
      { name: 'London', lat: 51.5074, lng: -0.1278, source: jsc },
      { name: 'Tokyo', lat: 35.6762, lng: 139.6503, source: jsc },
      { name: 'Moscow', lat: 55.7558, lng: 37.6173, source: jsc },
      // ARC connections
      { name: 'Sydney', lat: -33.8688, lng: 151.2093, source: arc },
      { name: 'Perth', lat: -31.9505, lng: 115.8605, source: arc },
      { name: 'Canberra', lat: -35.2809, lng: 149.1300, source: arc },
    ].map(target => ({
      startLat: target.source.lat,
      startLng: target.source.lng,
      endLat: target.lat,
      endLng: target.lng,
      bandwidth: 500,
      source: target.source.id,
      target: target.name,
      isInternational: true,
    }));

    setArcs([...connections, ...internationalConnections]);

    // Set initial camera position
    if (globeEl.current) {
      globeEl.current.controls().autoRotate = true;
      globeEl.current.controls().autoRotateSpeed = 0.22;
      globeEl.current.pointOfView({ lat: 20, lng: -77, altitude: 2 });
    }
  }, []);

  return (
    <div style={{ position: 'fixed', left: 0, right: 0, top: 0, bottom: 0 }}>
      <Globe
        ref={globeEl}
        globeImageUrl={globeImage}
        backgroundColor="rgba(0,0,0,0)"
        atmosphereColor="#4facfe"
        atmosphereAltitude={0.2}
        arcsData={arcs}
        arcColor={(d: any) => d.isInternational ? '#853434' : '#3778b1'}
        arcAltitude={0.15}
        arcStroke={0.44}
        arcDashLength={0.6}
        arcDashGap={0.65}
        arcDashAnimateTime={2200}
        pointsData={locations}
        pointColor={() => '#4facfe'}
        pointAltitude={0}
        pointRadius={0.25}
        pointsMerge={true}
        width={window.innerWidth}
        height={window.innerHeight}
      />
    </div>
  );
};

export default BgGlobe; 

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

  // NASA locations
  const locations: NASALocation[] = [
    { id: 'HQ', name: 'NASA Headquarters', lat: 38.9072, lng: -77.0365 },
    { id: 'JSC', name: 'Johnson Space Center', lat: 29.7604, lng: -95.3698 },
    { id: 'KSC', name: 'Kennedy Space Center', lat: 28.4059, lng: -80.6081 },
    { id: 'MSFC', name: 'Marshall Space Flight Center', lat: 34.7291, lng: -86.5861 },
    { id: 'GSFC', name: 'Goddard Space Flight Center', lat: 38.9967, lng: -76.8484 },
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

    // Add some international connections from JSC
    const jsc = locations.find(loc => loc.id === 'JSC')!;
    const internationalConnections = [
      { name: 'London', lat: 51.5074, lng: -0.1278 },
      { name: 'Tokyo', lat: 35.6762, lng: 139.6503 },
      { name: 'Moscow', lat: 55.7558, lng: 37.6173 },
    ].map(target => ({
      startLat: jsc.lat,
      startLng: jsc.lng,
      endLat: target.lat,
      endLng: target.lng,
      bandwidth: 500,
      source: 'JSC',
      target: target.name,
      isInternational: true,
    }));

    setArcs([...connections, ...internationalConnections]);

    // Set initial camera position
    if (globeEl.current) {
      globeEl.current.controls().autoRotate = true;
      globeEl.current.controls().autoRotateSpeed = 0.5;
      globeEl.current.pointOfView({ lat: 39.6, lng: -98.5, altitude: 2.5 });
    }
  }, []);

  return (
    <div style={{ position: 'fixed', left: 0, right: 0, top: 0, bottom: 0 }}>
      <Globe
        ref={globeEl}
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
        backgroundColor="rgba(0,0,0,0)"
        atmosphereColor="#4facfe"
        atmosphereAltitude={0.25}
        arcsData={arcs}
        arcColor={(d: any) => d.isInternational ? '#ff4b4b' : '#4facfe'}
        arcAltitude={0.3}
        arcStroke={0.5}
        arcDashLength={0.5}
        arcDashGap={0.5}
        arcDashAnimateTime={2000}
        pointsData={locations}
        pointColor={() => '#4facfe'}
        pointAltitude={0}
        pointRadius={0.05}
        pointsMerge={true}
        width={window.innerWidth}
        height={window.innerHeight}
      />
    </div>
  );
};

export default BgGlobe; 
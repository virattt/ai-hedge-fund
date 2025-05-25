import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import createGlobe from 'cobe';

function Globe() {
  const canvasRef = useRef(null);
  const [markers, setMarkers] = useState([]);
  const [events, setEvents] = useState([]);

  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;
    const globe = createGlobe(canvas, {
      devicePixelRatio: 2,
      width: 600,
      height: 600,
      phi: 0,
      theta: 0,
      dark: 1,
      diffuse: 1.2,
      mapSamples: 16000,
      mapBrightness: 6,
      baseColor: [0.3, 0.3, 0.3],
      markerColor: [0.1, 0.8, 0.1],
      glowColor: [1, 1, 1],
      markers
    });

    return () => globe.destroy();
  }, [markers]);

  useEffect(() => {
    fetch('/timeline.json')
      .then(res => res.json())
      .then(data => {
        const m = data.map((_, idx) => ({
          location: [0, (idx / data.length) * 360 - 180],
          size: 0.1,
        }));
        setMarkers(m);
        setEvents(data);
      })
      .catch(() => {
        /* ignore errors */
      });
  }, []);

  const project = (lat, lon) => {
    const phi = (lat * Math.PI) / 180;
    const theta = (lon * Math.PI) / 180;
    const x = Math.cos(phi) * Math.sin(theta);
    const y = Math.sin(phi);
    const z = Math.cos(phi) * Math.cos(theta);
    if (z < 0) return null;
    const r = 300; // canvas width / 2
    return { left: 300 + x * r, top: 300 - y * r };
  };

  return (
    <div style={{ position: 'relative', width: 600, height: 600 }}>
      <canvas ref={canvasRef} width={600} height={600}></canvas>
      {events.map((ev, idx) => {
        const pos = project(0, (idx / events.length) * 360 - 180);
        if (!pos) return null;
        return (
          <div
            key={idx}
            title={`${ev.year}: ${ev.event}`}
            style={{
              position: 'absolute',
              left: pos.left,
              top: pos.top,
              transform: 'translate(-50%, -50%)',
              pointerEvents: 'auto',
            }}
          >
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                backgroundColor: '#ff0',
              }}
            ></div>
          </div>
        );
      })
    </div>
  );
}

createRoot(document.getElementById('root')).render(<Globe />);

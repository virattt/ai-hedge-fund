import React, { useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import createGlobe from 'cobe';

function Globe() {
  const canvasRef = useRef(null);
  const infoRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;
    const info = document.getElementById('info');
    let rotation = 0;

    fetch('./timeline.json')
      .then((res) => res.json())
      .then((data) => {
        const count = data.length;
        const markers = data.map((e, i) => {
          const lat = 0;
          const lng = (360 / count) * i;
          return { location: [lat, lng], size: 0.1, label: `${e.year}: ${e.event}` };
        });

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
          markers,
          onRender: (state) => {
            rotation += 0.005;
            state.phi = rotation;
          },
          onMouseOver: (marker) => {
            if (info) info.textContent = marker.label;
          },
          onMouseOut: () => {
            if (info) info.textContent = '';
          }
        });

        return () => globe.destroy();
      });
  }, []);

  return <canvas ref={canvasRef}></canvas>;
}

createRoot(document.getElementById('root')).render(<Globe />);

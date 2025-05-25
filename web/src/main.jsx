import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import createGlobe from 'cobe';

function Globe() {
  const canvasRef = useRef(null);
  const [markers, setMarkers] = useState([]);

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
      })
      .catch(() => {
        /* ignore errors */
      });
  }, []);

  return <canvas ref={canvasRef}></canvas>;
}

createRoot(document.getElementById('root')).render(<Globe />);

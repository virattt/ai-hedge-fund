<import { createRoot } from 'react-dom/client';
import createGlobe from 'cobe';

function Globe() {
  const canvasRef = useRef(null);


  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;

      });
  }, []);

  return <canvas ref={canvasRef}></canvas>;
}

createRoot(document.getElementById('root')).render(<Globe />);

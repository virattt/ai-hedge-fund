import { useEffect, useRef, useState } from 'react';

interface UseResizableOptions {
  minWidth?: number;
  maxWidth?: number;
  defaultWidth?: number;
  minHeight?: number;
  maxHeight?: number;
  defaultHeight?: number;
  side?: 'left' | 'right' | 'bottom';
}

export function useResizable({
  minWidth = 200,
  maxWidth = 500,
  defaultWidth = 250,
  minHeight = 200,
  maxHeight = 600,
  defaultHeight = 300,
  side = 'left'
}: UseResizableOptions = {}) {
  const [width, setWidth] = useState(defaultWidth);
  const [height, setHeight] = useState(defaultHeight);
  const [isDragging, setIsDragging] = useState(false);
  const elementRef = useRef<HTMLDivElement>(null);
  // Add a ref for tracking dragging state - updates synchronously unlike state
  const isDraggingRef = useRef(false);

  // Handle manual resizing with mouse
  const startResize = (e: React.MouseEvent) => {
    e.preventDefault();
    // Set both the ref (for immediate use in mousemove) and state (for rendering)
    isDraggingRef.current = true;
    setIsDragging(true);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', stopResize);
  };

  const handleMouseMove = (e: MouseEvent) => {
    // Use the ref value instead of state for checking
    if (!isDraggingRef.current) return;
    
    // Get element's position
    const elementRect = elementRef.current?.getBoundingClientRect();
    if (!elementRect) return;
    
    if (side === 'bottom') {
      // For bottom panel: dragging up decreases height
      const newHeight = elementRect.bottom - e.clientY;
      const clampedHeight = Math.max(minHeight, Math.min(maxHeight, newHeight));
      setHeight(clampedHeight);
    } else {
      // For horizontal resizing (left/right sidebars)
      let newWidth;
      if (side === 'left') {
        // For left sidebar: dragging right increases width
        newWidth = e.clientX - elementRect.left;
      } else {
        // For right sidebar: dragging left decreases width
        newWidth = elementRect.right - e.clientX;
      }
      
      // Calculate new width (limit between minWidth and maxWidth)
      newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
      
      setWidth(newWidth);
    }
  };

  const stopResize = () => {
    // Update both ref and state
    isDraggingRef.current = false;
    setIsDragging(false);
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', stopResize);
  };

  // Clean up event listeners when component unmounts
  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', stopResize);
    };
  }, []);

  return {
    width,
    height,
    isDragging,
    elementRef,
    startResize
  };
} 
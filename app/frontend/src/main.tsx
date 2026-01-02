import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import { NodeProvider } from './contexts/node-context';
import { ThemeProvider } from './providers/theme-provider';

import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <NodeProvider>
        <App />
      </NodeProvider>
    </ThemeProvider>
  </React.StrictMode>
);

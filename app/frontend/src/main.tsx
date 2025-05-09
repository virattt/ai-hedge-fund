import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import { NodeStatusProvider } from './contexts/node-status-context';
import { ThemeProvider } from './contexts/theme-provider';

import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <NodeStatusProvider>
        <App />
      </NodeStatusProvider>
    </ThemeProvider>
  </React.StrictMode>
);

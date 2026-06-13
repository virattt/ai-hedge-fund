import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import { NodeProvider } from './contexts/node-context';
import { I18nProvider } from './i18n/i18n-provider';
import { ThemeProvider } from './providers/theme-provider';

import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <I18nProvider>
        <NodeProvider>
          <App />
        </NodeProvider>
      </I18nProvider>
    </ThemeProvider>
  </React.StrictMode>
);

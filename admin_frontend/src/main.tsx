import React from 'react';
import ReactDOM from 'react-dom/client';
import { NextUIProvider } from '@nextui-org/react';
import { ThemeProvider as NextThemesProvider } from 'next-themes';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <NextThemesProvider attribute="class" defaultTheme="light">
      <NextUIProvider>
        <BrowserRouter basename="/admin">
          <App />
        </BrowserRouter>
      </NextUIProvider>
    </NextThemesProvider>
  </React.StrictMode>
); 
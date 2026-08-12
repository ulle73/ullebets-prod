import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './app/App';
import './styles/global.css';
import './styles/pages.css';
import './styles/live-data.css';
import './styles/drilldowns.css';
import './styles/workflow-pages.css';
import './styles/shell-hardening.css';

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root');
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } });
createRoot(root).render(<StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></StrictMode>);

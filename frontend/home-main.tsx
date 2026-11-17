import React from 'react';
import { createRoot } from 'react-dom/client';
import { HomeView } from './HomeView';
import './style.css';

createRoot(document.getElementById('root')!).render(<HomeView />);

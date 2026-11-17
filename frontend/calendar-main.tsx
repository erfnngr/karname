import React from 'react';
import { createRoot } from 'react-dom/client';
import { CalendarView } from './CalendarView';
import './style.css';

createRoot(document.getElementById('root')!).render(<CalendarView />);

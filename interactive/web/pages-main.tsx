import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './app/globals.css';
import { RefusalObservatory } from './components/refusal-observatory';

const root = document.getElementById('root');

if (!root) {
  throw new Error('Static site root element is missing.');
}

createRoot(root).render(
  <StrictMode>
    <RefusalObservatory />
  </StrictMode>,
);

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import AuthStatus from './AuthStatus';

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><AuthStatus/><App/></React.StrictMode>);

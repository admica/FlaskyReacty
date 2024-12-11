// PATH: src/routes/NetworkRoute.tsx

import { Navigate } from 'react-router-dom';
import { NetworkPage } from '../components/network/NetworkPage';

const NetworkRoute = () => {
  const isAuthenticated = localStorage.getItem('token') !== null;
  
  return isAuthenticated ? <NetworkPage /> : <Navigate to="/login" />;
};

export default NetworkRoute; 
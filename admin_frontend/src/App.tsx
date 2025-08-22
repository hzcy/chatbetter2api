import React from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import LoginPage from './pages/Login';
import AdminLayout from './layout/AdminLayout';
import TokensPage from './pages/Tokens';

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={<RequireAuthWrapper />}
      />
    </Routes>
  );
};

const RequireAuthWrapper: React.FC = () => {
  const navigate = useNavigate();
  const token = localStorage.getItem('adminToken');
  React.useEffect(() => {
    if (!token) {
      navigate('/login');
    }
  }, [token, navigate]);

  if (!token) return null;

  return (
    <AdminLayout>
      <Routes>
        <Route path="tokens" element={<TokensPage />} />
        <Route path="*" element={<Navigate to="tokens" replace />} />
      </Routes>
    </AdminLayout>
  );
};

export default App; 
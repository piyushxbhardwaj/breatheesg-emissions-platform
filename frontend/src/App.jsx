import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import UploadsPage from './pages/UploadsPage';
import ReviewQueuePage from './pages/ReviewQueuePage';
import ApprovedRecordsPage from './pages/ApprovedRecordsPage';
import { API_BASE_URL } from './config';

export default function App() {
  const [activePage, setActivePage] = useState('uploads');
  const [tenants, setTenants] = useState([]);
  const [activeTenantId, setActiveTenantId] = useState('');
  const [loadingTenants, setLoadingTenants] = useState(true);
  const [toasts, setToasts] = useState([]);

  // Toast Helper
  const addToast = (message, type = 'success') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  // Fetch Tenants on Load
  useEffect(() => {
    const fetchTenants = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/tenants/`);
        if (response.ok) {
          const data = await response.json();
          setTenants(data);
          if (data.length > 0) {
            // Set initial active tenant
            setActiveTenantId(data[0].id);
          }
        } else {
          addToast('Failed to load tenants list.', 'error');
        }
      } catch (err) {
        addToast('Network error fetching tenants.', 'error');
      } finally {
        setLoadingTenants(false);
      }
    };
    fetchTenants();
  }, []);

  const getActiveTenantName = () => {
    const tenant = tenants.find(t => t.id === activeTenantId);
    return tenant ? tenant.name : 'Select Tenant';
  };

  const renderActivePage = () => {
    if (loadingTenants || !activeTenantId) {
      return (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Loading active tenant database context...
        </div>
      );
    }

    switch (activePage) {
      case 'uploads':
        return <UploadsPage activeTenantId={activeTenantId} addToast={addToast} />;
      case 'review':
        return <ReviewQueuePage activeTenantId={activeTenantId} addToast={addToast} />;
      case 'approved':
        return <ApprovedRecordsPage activeTenantId={activeTenantId} addToast={addToast} />;
      default:
        return <UploadsPage activeTenantId={activeTenantId} addToast={addToast} />;
    }
  };

  const getPageTitle = () => {
    switch (activePage) {
      case 'uploads': return 'Data Ingestion Console';
      case 'review': return 'Analyst Review Queue';
      case 'approved': return 'Consolidated Audit Ledger';
      default: return 'ESG Ingestion Dashboard';
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <Sidebar activePage={activePage} setActivePage={setActivePage} />

      {/* Main Panel */}
      <div className="main-content">
        
        {/* Header Toolbar */}
        <header className="main-header">
          <div className="header-title">
            <h1>{getPageTitle()}</h1>
          </div>
          
          <div className="header-actions">
            {/* Tenant switcher context */}
            <div className="tenant-switcher-container">
              <span className="switcher-label">Active Context:</span>
              <select 
                className="select-switcher" 
                value={activeTenantId}
                onChange={(e) => {
                  setActiveTenantId(e.target.value);
                  addToast(`Switched active context to: ${tenants.find(t => t.id === e.target.value)?.name}`, 'success');
                }}
                disabled={loadingTenants}
              >
                {tenants.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            
            {/* Analyst profile badge */}
            <div className="analyst-profile">
              <div className="avatar">A</div>
              <span>Analyst Reviewer</span>
            </div>
          </div>
        </header>

        {/* Content body layout */}
        <main className="content-body">
          {renderActivePage()}
        </main>
      </div>

      {/* Toast Alert Overlays */}
      <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 1000, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            <span>{t.type === 'success' ? '✅' : '⚠️'}</span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

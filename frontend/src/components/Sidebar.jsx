import React from 'react';

export default function Sidebar({ activePage, setActivePage }) {
  return (
    <div className="sidebar">
      <div>
        <div className="sidebar-header">
          <div className="logo">
            <span>🌍</span> BreatheESG Ingest
          </div>
        </div>
        <ul className="sidebar-menu">
          <li 
            className={`menu-item ${activePage === 'uploads' ? 'active' : ''}`}
            onClick={() => setActivePage('uploads')}
          >
            <span>📥</span> Upload Datasets
          </li>
          <li 
            className={`menu-item ${activePage === 'review' ? 'active' : ''}`}
            onClick={() => setActivePage('review')}
          >
            <span>⚖️</span> Review Queue
          </li>
          <li 
            className={`menu-item ${activePage === 'approved' ? 'active' : ''}`}
            onClick={() => setActivePage('approved')}
          >
            <span>🛡️</span> Approved Records
          </li>
        </ul>
      </div>
      <div className="sidebar-footer">
        <p>ESG Ingestion Platform</p>
        <p>Version 1.0.0 (Audit-Locked)</p>
      </div>
    </div>
  );
}

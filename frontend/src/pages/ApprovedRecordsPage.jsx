import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

export default function ApprovedRecordsPage({ activeTenantId, addToast }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Filters
  const [filterScope, setFilterScope] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterFacility, setFilterFacility] = useState('');

  // Selected Record (Audit Log Drawer)
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  const fetchRecords = async () => {
    if (!activeTenantId) return;
    setLoading(true);
    try {
      let url = `${API_BASE_URL}/records/?review_status=APPROVED`;
      if (filterScope) url += `&scope=${filterScope}`;
      if (filterCategory) url += `&category=${filterCategory}`;
      if (filterFacility) url += `&facility=${filterFacility}`;

      const response = await fetch(url, {
        headers: {
          'X-Tenant-ID': activeTenantId,
        }
      });
      if (response.ok) {
        const data = await response.json();
        setRecords(data);
      } else {
        addToast('Failed to load approved records', 'error');
      }
    } catch (err) {
      addToast('Network error loading records', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecords();
  }, [activeTenantId, filterScope, filterCategory, filterFacility]);

  // Open drawer for audit trail inspection
  const openAuditDrawer = async (record) => {
    setSelectedRecord(record);
    setDrawerOpen(true);
    
    setLoadingAudit(true);
    try {
      const response = await fetch(`${API_BASE_URL}/records/${record.id}/audit-log/`, {
        headers: {
          'X-Tenant-ID': activeTenantId,
        }
      });
      if (response.ok) {
        const data = await response.json();
        setAuditLogs(data);
      }
    } catch (err) {
      addToast('Failed to load audit history', 'error');
    } finally {
      setLoadingAudit(false);
    }
  };

  const closeAuditDrawer = () => {
    setDrawerOpen(false);
    setSelectedRecord(null);
  };

  // Emissions Calculations
  const scope1Total = records
    .filter(r => r.scope === 1)
    .reduce((sum, r) => sum + parseFloat(r.normalized_quantity_co2e), 0);

  const scope2Total = records
    .filter(r => r.scope === 2)
    .reduce((sum, r) => sum + parseFloat(r.normalized_quantity_co2e), 0);

  const scope3Total = records
    .filter(r => r.scope === 3)
    .reduce((sum, r) => sum + parseFloat(r.normalized_quantity_co2e), 0);

  const grandTotal = scope1Total + scope2Total + scope3Total;

  const getScopeBadge = (scope) => {
    switch (scope) {
      case 1: return <span className="badge badge-scope-1">Scope 1</span>;
      case 2: return <span className="badge badge-scope-2">Scope 2</span>;
      case 3: return <span className="badge badge-scope-3">Scope 3</span>;
      default: return <span className="badge">{scope}</span>;
    }
  };

  return (
    <div>
      {/* Metrics Cards */}
      <div className="metric-grid">
        <div className="metric-card" style={{ borderLeft: '4px solid #1e40af' }}>
          <div className="metric-title">Scope 1 (Direct)</div>
          <div className="metric-value">{scope1Total.toFixed(3)}</div>
          <div className="metric-subtitle">Metric Tonnes CO2e</div>
        </div>
        <div className="metric-card" style={{ borderLeft: '4px solid #86198f' }}>
          <div className="metric-title">Scope 2 (Indirect - Utilities)</div>
          <div className="metric-value">{scope2Total.toFixed(3)}</div>
          <div className="metric-subtitle">Metric Tonnes CO2e</div>
        </div>
        <div className="metric-card" style={{ borderLeft: '4px solid #9a3412' }}>
          <div className="metric-title">Scope 3 (Business Travel)</div>
          <div className="metric-value">{scope3Total.toFixed(3)}</div>
          <div className="metric-subtitle">Metric Tonnes CO2e</div>
        </div>
        <div className="metric-card" style={{ borderLeft: '4px solid var(--primary)', backgroundColor: 'var(--neutral-50)' }}>
          <div className="metric-title" style={{ color: 'var(--primary)', fontWeight: 'bold' }}>Total Carbon footprint</div>
          <div className="metric-value" style={{ color: 'var(--primary)' }}>{grandTotal.toFixed(3)}</div>
          <div className="metric-subtitle">tCO2e Consolidated Footprint</div>
        </div>
      </div>

      {/* Approved Records Table Card */}
      <div className="table-card">
        <div className="table-header-toolbar">
          <div className="toolbar-title">Locked Audit-Ready Ledger</div>
          
          <div className="toolbar-filters">
            <select 
              className="filter-select" 
              value={filterScope} 
              onChange={(e) => setFilterScope(e.target.value)}
            >
              <option value="">All Scopes</option>
              <option value="1">Scope 1</option>
              <option value="2">Scope 2</option>
              <option value="3">Scope 3</option>
            </select>
            
            <input 
              type="text" 
              className="filter-input" 
              placeholder="Category" 
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
            />
            
            <input 
              type="text" 
              className="filter-input" 
              placeholder="Plant/Facility ID" 
              value={filterFacility}
              onChange={(e) => setFilterFacility(e.target.value)}
            />

            <button className="btn btn-secondary btn-sm" onClick={fetchRecords}>🔄 Refresh</button>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Loading approved records...
          </div>
        ) : records.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            No approved records found. Go to Review Queue to audit and lock records.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Scope</th>
                <th>Category</th>
                <th>Facility / Plant</th>
                <th>Activity Description</th>
                <th>Reported Quantity</th>
                <th>Audited Carbon (tCO2e)</th>
                <th>Audit Period</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec) => (
                <tr 
                  key={rec.id} 
                  onClick={() => openAuditDrawer(rec)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>{getScopeBadge(rec.scope)}</td>
                  <td style={{ fontWeight: 500 }}>{rec.category}</td>
                  <td>{rec.facility_or_plant}</td>
                  <td>{rec.activity_type}</td>
                  <td>
                    {parseFloat(rec.original_quantity).toLocaleString()} {rec.original_unit}
                  </td>
                  <td style={{ fontWeight: 600, color: 'var(--primary)' }}>
                    {parseFloat(rec.normalized_quantity_co2e).toFixed(4)}
                  </td>
                  <td style={{ fontSize: '13px' }}>
                    {rec.start_date === rec.end_date ? rec.start_date : `${rec.start_date} to ${rec.end_date}`}
                  </td>
                  <td>
                    <span className="badge badge-completed" style={{ gap: '4px' }}>
                      🔒 Locked
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Audit Inspection Drawer (Read-Only) */}
      {drawerOpen && selectedRecord && (
        <div className="drawer-backdrop" onClick={closeAuditDrawer}>
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <h2>🔒 Immutable Audit Record</h2>
              <button className="drawer-close" onClick={closeAuditDrawer}>&times;</button>
            </div>
            
            <div className="drawer-body">
              <div className="warning-box" style={{ backgroundColor: 'var(--success-light)', borderColor: '#bbf7d0', color: '#166534' }}>
                <div className="warning-box-title" style={{ color: '#166534' }}>Verified & Locked for Regulatory Audit</div>
                This record was approved. It has been cryptographically locked in the ledger database and cannot be modified.
              </div>

              {/* Comparison Section (Raw vs Normalized) */}
              <div className="comparison-box">
                <div className="comparison-title">Original Ingest Raw Record</div>
                <div className="comparison-grid">
                  {Object.entries(selectedRecord.raw_data || {}).map(([key, val]) => (
                    <div className="comparison-cell" key={key}>
                      <span className="comparison-label">{key}</span>
                      <span className="comparison-value">{String(val) || '(blank)'}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Fields info */}
              <div className="form-group">
                <label className="form-label">Scope Classification</label>
                <input type="text" className="form-control" value={selectedRecord.scope_display} readOnly />
              </div>

              <div className="form-group">
                <label className="form-label">Activity Category</label>
                <input type="text" className="form-control" value={selectedRecord.category} readOnly />
              </div>

              <div className="form-group">
                <label className="form-label">Activity Description</label>
                <input type="text" className="form-control" value={selectedRecord.activity_type} readOnly />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label className="form-label">Audited Quantity</label>
                  <input type="text" className="form-control" value={parseFloat(selectedRecord.original_quantity).toLocaleString()} readOnly />
                </div>
                <div className="form-group">
                  <label className="form-label">Unit of Measure</label>
                  <input type="text" className="form-control" value={selectedRecord.original_unit} readOnly />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label className="form-label">Start Date</label>
                  <input type="text" className="form-control" value={selectedRecord.start_date} readOnly />
                </div>
                <div className="form-group">
                  <label className="form-label">End Date</label>
                  <input type="text" className="form-control" value={selectedRecord.end_date} readOnly />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Facility / Cost Center / Plant</label>
                <input type="text" className="form-control" value={selectedRecord.facility_or_plant} readOnly />
              </div>

              <div className="form-group">
                <label className="form-label">Locked Carbon Footprint</label>
                <input 
                  type="text" 
                  className="form-control" 
                  value={`${parseFloat(selectedRecord.normalized_quantity_co2e).toFixed(6)} tCO2e`} 
                  readOnly 
                  style={{ fontWeight: 'bold', color: 'var(--success)' }}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Factor Source: {selectedRecord.factor_reference_details?.activity_type} ({selectedRecord.factor_reference_details?.source_name}) - {selectedRecord.factor_reference_details?.factor_value} {selectedRecord.factor_reference_details?.unit}
                </span>
              </div>

              {/* Audit history list */}
              <div style={{ marginTop: '10px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px' }}>Complete Ledger Lifecycle Audit</h3>
                {loadingAudit ? (
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Loading logs...</div>
                ) : (
                  <div className="audit-list">
                    {auditLogs.map((log) => (
                      <div key={log.id} className={`audit-item action-${log.action_type.toLowerCase()}`}>
                        <div className="audit-meta">
                          {log.performed_by} at {log.performed_at_formatted}
                        </div>
                        <div className="audit-action-title">{log.action_display}</div>
                        {log.comment && <div className="audit-comment">"{log.comment}"</div>}
                        {log.changes && Object.keys(log.changes).length > 0 && (
                          <div className="audit-diffs">
                            {Object.entries(log.changes).map(([field, delta]) => (
                              <div key={field}>
                                {field}: {delta.before} &rarr; {delta.after}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="drawer-footer">
              <button className="btn btn-secondary" onClick={closeAuditDrawer} style={{ width: '100%' }}>
                Close Audit Inspection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

export default function ReviewQueuePage({ activeTenantId, addToast }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  
  // Filters
  const [filterScope, setFilterScope] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterFacility, setFilterFacility] = useState('');
  const [filterSuspicious, setFilterSuspicious] = useState('');

  // Drawer Edit State
  const [editingRecord, setEditingRecord] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  
  // Edit Form Fields
  const [editQty, setEditQty] = useState('');
  const [editUnit, setEditUnit] = useState('');
  const [editStartDate, setEditStartDate] = useState('');
  const [editEndDate, setEditEndDate] = useState('');
  const [editFacility, setEditFacility] = useState('');
  const [editComment, setEditComment] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);

  // Bulk comments
  const [bulkApproving, setBulkApproving] = useState(false);

  const fetchRecords = async () => {
    if (!activeTenantId) return;
    setLoading(true);
    try {
      // Build query string
      let url = `${API_BASE_URL}/records/?review_status=PENDING_REVIEW`;
      if (filterScope) url += `&scope=${filterScope}`;
      if (filterCategory) url += `&category=${filterCategory}`;
      if (filterFacility) url += `&facility=${filterFacility}`;
      if (filterSuspicious) url += `&suspicious_flag=${filterSuspicious}`;

      const response = await fetch(url, {
        headers: {
          'X-Tenant-ID': activeTenantId,
        }
      });
      if (response.ok) {
        const data = await response.json();
        setRecords(data);
      } else {
        addToast('Failed to load review queue', 'error');
      }
    } catch (err) {
      addToast('Network error loading queue', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecords();
    setSelectedIds([]);
  }, [activeTenantId, filterScope, filterCategory, filterFacility, filterSuspicious]);

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedIds(records.map(r => r.id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleSelectRow = (id, checked) => {
    if (checked) {
      setSelectedIds(prev => [...prev, id]);
    } else {
      setSelectedIds(prev => prev.filter(item => item !== id));
    }
  };

  // Open Edit Drawer
  const openEditDrawer = async (record) => {
    setEditingRecord(record);
    setEditQty(record.original_quantity);
    setEditUnit(record.original_unit);
    setEditStartDate(record.start_date);
    setEditEndDate(record.end_date);
    setEditFacility(record.facility_or_plant);
    setEditComment('');
    setDrawerOpen(true);
    setSelectedIds([]); // Deselect rows to prevent action overlay overlap
    
    // Fetch Audit Log for this record
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

  const closeEditDrawer = () => {
    setDrawerOpen(false);
    setEditingRecord(null);
  };

  // Save changes from drawer
  const handleSaveChanges = async () => {
    if (!editComment.strip()) {
      addToast('Please enter an audit comment explaining your modifications.', 'error');
      return;
    }
    
    setSavingEdit(true);
    try {
      const response = await fetch(`${API_BASE_URL}/records/${editingRecord.id}/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': activeTenantId,
        },
        body: JSON.stringify({
          original_quantity: parseFloat(editQty),
          original_unit: editUnit,
          start_date: editStartDate,
          end_date: editEndDate,
          facility_or_plant: editFacility,
          comment: editComment,
          performed_by: 'Analyst (UI)',
        })
      });

      if (response.ok) {
        addToast('Record updated successfully, emissions recalculated.', 'success');
        // Refresh editing record or close drawer
        closeEditDrawer();
        fetchRecords();
      } else {
        const errData = await response.json();
        addToast(errData.error || 'Failed to update record.', 'error');
      }
    } catch (err) {
      addToast('Network error updating record', 'error');
    } finally {
      setSavingEdit(false);
    }
  };

  // Approve single record from drawer
  const handleApproveSingle = async () => {
    setSavingEdit(true);
    try {
      const response = await fetch(`${API_BASE_URL}/records/${editingRecord.id}/approve/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': activeTenantId,
        },
        body: JSON.stringify({
          comment: editComment || 'Analyst approved and locked record.',
          performed_by: 'Analyst (UI)',
        })
      });

      if (response.ok) {
        addToast('Record approved and locked for audit.', 'success');
        closeEditDrawer();
        fetchRecords();
      } else {
        addToast('Failed to approve record.', 'error');
      }
    } catch (err) {
      addToast('Network error during approval', 'error');
    } finally {
      setSavingEdit(false);
    }
  };

  // Reject single record from drawer
  const handleRejectSingle = async () => {
    if (!editComment.trim()) {
      addToast('Rejection requires a brief comment explaining the reason.', 'error');
      return;
    }
    
    setSavingEdit(true);
    try {
      const response = await fetch(`${API_BASE_URL}/records/${editingRecord.id}/reject/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': activeTenantId,
        },
        body: JSON.stringify({
          comment: editComment,
          performed_by: 'Analyst (UI)',
        })
      });

      if (response.ok) {
        addToast('Record marked as rejected in the queue.', 'warning');
        closeEditDrawer();
        fetchRecords();
      } else {
        addToast('Failed to reject record.', 'error');
      }
    } catch (err) {
      addToast('Network error during rejection', 'error');
    } finally {
      setSavingEdit(false);
    }
  };

  // Bulk approval of selected records
  const handleBulkApprove = async () => {
    if (selectedIds.length === 0) return;
    setBulkApproving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/records/bulk-approve/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': activeTenantId,
        },
        body: JSON.stringify({
          record_ids: selectedIds,
          comment: 'Bulk approval via Review Queue dashboard.',
          performed_by: 'Analyst (UI)',
        })
      });

      const resData = await response.json();
      if (response.ok) {
        addToast(`Successfully approved and locked ${resData.approved_count} records.`, 'success');
        setSelectedIds([]);
        fetchRecords();
      } else {
        addToast(resData.error || 'Bulk approval failed.', 'error');
      }
    } catch (err) {
      addToast('Network error performing bulk action', 'error');
    } finally {
      setBulkApproving(false);
    }
  };

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
      <div className="table-card">
        <div className="table-header-toolbar">
          <div className="toolbar-title">Review Queue</div>
          
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
              placeholder="Category (e.g. Flight)" 
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
            
            <select 
              className="filter-select" 
              value={filterSuspicious} 
              onChange={(e) => setFilterSuspicious(e.target.value)}
            >
              <option value="">All Values</option>
              <option value="true">⚠️ Suspicious Only</option>
              <option value="false">Normal Only</option>
            </select>

            <button className="btn btn-secondary btn-sm" onClick={fetchRecords}>🔄 Refresh</button>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Loading pending records...
          </div>
        ) : records.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            No records pending review in the queue. Ingest datasets or adjust filters.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '40px' }}>
                  <input 
                    type="checkbox" 
                    onChange={handleSelectAll}
                    checked={selectedIds.length === records.length && records.length > 0}
                  />
                </th>
                <th>Scope</th>
                <th>Category</th>
                <th>Facility / Plant</th>
                <th>Activity Description</th>
                <th>Original Quantity</th>
                <th>Normalized (tCO2e)</th>
                <th>Date Range</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec) => (
                <tr 
                  key={rec.id} 
                  style={{ cursor: 'pointer' }}
                >
                  <td onClick={(e) => e.stopPropagation()}>
                    <input 
                      type="checkbox" 
                      checked={selectedIds.includes(rec.id)}
                      onChange={(e) => handleSelectRow(rec.id, e.target.checked)}
                    />
                  </td>
                  <td onClick={() => openEditDrawer(rec)}>{getScopeBadge(rec.scope)}</td>
                  <td onClick={() => openEditDrawer(rec)} style={{ fontWeight: 500 }}>{rec.category}</td>
                  <td onClick={() => openEditDrawer(rec)}>{rec.facility_or_plant}</td>
                  <td onClick={() => openEditDrawer(rec)}>{rec.activity_type}</td>
                  <td onClick={() => openEditDrawer(rec)}>
                    {parseFloat(rec.original_quantity).toLocaleString()} {rec.original_unit}
                  </td>
                  <td onClick={() => openEditDrawer(rec)} style={{ fontWeight: 600, color: 'var(--neutral-800)' }}>
                    {parseFloat(rec.normalized_quantity_co2e).toFixed(4)}
                  </td>
                  <td onClick={() => openEditDrawer(rec)} style={{ fontSize: '13px' }}>
                    {rec.start_date === rec.end_date ? rec.start_date : `${rec.start_date} to ${rec.end_date}`}
                  </td>
                  <td onClick={() => openEditDrawer(rec)}>
                    {rec.suspicious_flag ? (
                      <span className="suspicious-pill" title={rec.suspicious_reasons.join(', ')}>
                        ⚠️ Suspicious
                      </span>
                    ) : (
                      <span className="badge badge-pending">Review</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Bulk Approval Float Action Bar */}
      {selectedIds.length > 0 && (
        <div className="bulk-bar">
          <div className="bulk-info">
            <span>⚙️ {selectedIds.length} records selected for bulk operation</span>
          </div>
          <div className="bulk-actions">
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={() => setSelectedIds([])}
              style={{ color: 'white', borderColor: 'var(--neutral-700)', backgroundColor: 'var(--neutral-800)' }}
            >
              Cancel
            </button>
            <button 
              className="btn btn-success btn-sm" 
              onClick={handleBulkApprove}
              disabled={bulkApproving}
            >
              {bulkApproving ? 'Locking records...' : '✅ Approve & Lock Selected'}
            </button>
          </div>
        </div>
      )}

      {/* Edit Drawer Panel */}
      {drawerOpen && editingRecord && (
        <div className="drawer-backdrop" onClick={closeEditDrawer}>
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <h2>Review Ingested Record</h2>
              <button className="drawer-close" onClick={closeEditDrawer}>&times;</button>
            </div>
            
            <div className="drawer-body">
              {editingRecord.suspicious_flag && (
                <div className="warning-box">
                  <div className="warning-box-title">⚠️ Validation Alert Flags</div>
                  <ul>
                    {editingRecord.suspicious_reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Comparison Section (Raw vs Normalized) */}
              <div className="comparison-box">
                <div className="comparison-title">Raw Ingest Row Mapping</div>
                <div className="comparison-grid">
                  {Object.entries(editingRecord.raw_data || {}).map(([key, val]) => (
                    <div className="comparison-cell" key={key}>
                      <span className="comparison-label">{key}</span>
                      <span className="comparison-value">{String(val) || '(blank)'}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Edit Fields Form */}
              <div className="form-group">
                <label className="form-label">Activity Category</label>
                <input type="text" className="form-control" value={editingRecord.category} readOnly />
              </div>

              <div className="form-group">
                <label className="form-label">Activity Description</label>
                <input type="text" className="form-control" value={editingRecord.activity_type} readOnly />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label className="form-label">Original Qty</label>
                  <input 
                    type="number" 
                    className="form-control" 
                    value={editQty} 
                    onChange={(e) => setEditQty(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Original Unit</label>
                  <input 
                    type="text" 
                    className="form-control" 
                    value={editUnit} 
                    onChange={(e) => setEditUnit(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label className="form-label">Start Date</label>
                  <input 
                    type="date" 
                    className="form-control" 
                    value={editStartDate} 
                    onChange={(e) => setEditStartDate(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">End Date</label>
                  <input 
                    type="date" 
                    className="form-control" 
                    value={editEndDate} 
                    onChange={(e) => setEditEndDate(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Facility / Cost Center / Plant</label>
                <input 
                  type="text" 
                  className="form-control" 
                  value={editFacility} 
                  onChange={(e) => setEditFacility(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Calculated Carbon footprint</label>
                <input 
                  type="text" 
                  className="form-control" 
                  value={`${parseFloat(editingRecord.normalized_quantity_co2e).toFixed(6)} tCO2e`} 
                  readOnly 
                  style={{ fontWeight: 'bold', color: 'var(--primary)' }}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Factor Source: {editingRecord.factor_reference_details?.activity_type} ({editingRecord.factor_reference_details?.source_name}) - {editingRecord.factor_reference_details?.factor_value} {editingRecord.factor_reference_details?.unit}
                </span>
              </div>

              {/* Audit logs listing */}
              <div style={{ marginTop: '10px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px' }}>Audit Log & History</h3>
                {loadingAudit ? (
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Loading history...</div>
                ) : auditLogs.length === 0 ? (
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No previous changes recorded.</div>
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

              {/* Audit Reason Comment Input */}
              <div className="form-group" style={{ marginTop: '10px' }}>
                <label className="form-label">Audit Review Comment (Required to Save/Reject)</label>
                <textarea 
                  className="form-control" 
                  placeholder="Explain why edits were made or why this record is approved/rejected..."
                  rows="3"
                  value={editComment}
                  onChange={(e) => setEditComment(e.target.value)}
                  style={{ resize: 'vertical', fontFamily: 'var(--font-sans)', fontSize: '13px' }}
                />
              </div>
            </div>

            <div className="drawer-footer">
              <button 
                className="btn btn-secondary" 
                onClick={handleRejectSingle}
                disabled={savingEdit}
              >
                ❌ Reject
              </button>
              
              <button 
                className="btn btn-secondary" 
                onClick={handleSaveChanges} 
                disabled={savingEdit}
                style={{ border: '1px solid var(--primary)', color: 'var(--primary)' }}
              >
                💾 Save Adjustments
              </button>
              
              <button 
                className="btn btn-success" 
                onClick={handleApproveSingle}
                disabled={savingEdit}
              >
                ✅ Approve & Lock
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

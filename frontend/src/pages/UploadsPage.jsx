import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

export default function UploadsPage({ activeTenantId, addToast }) {
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [sourceType, setSourceType] = useState('SAP_FUEL');
  const [uploading, setUploading] = useState(false);

  const fetchUploads = async () => {
    if (!activeTenantId) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/uploads/`, {
        headers: {
          'X-Tenant-ID': activeTenantId,
        }
      });
      if (response.ok) {
        const data = await response.json();
        setUploads(data);
      } else {
        addToast('Failed to fetch uploads list', 'error');
      }
    } catch (err) {
      addToast('Network error fetching uploads', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUploads();
  }, [activeTenantId]);

  const handleFileChange = (e) => {
    if (e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      addToast('Please select a CSV file first.', 'error');
      return;
    }
    if (!activeTenantId) {
      addToast('No active tenant selected.', 'error');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('source_type', sourceType);
    formData.append('tenant_id', activeTenantId);
    formData.append('uploaded_by', 'Analyst (UI)');

    try {
      const response = await fetch(`${API_BASE_URL}/uploads/`, {
        method: 'POST',
        headers: {
          'X-Tenant-ID': activeTenantId,
        },
        body: formData,
      });

      const resData = await response.json();

      if (response.ok) {
        addToast(`Successfully uploaded: ${selectedFile.name}`, 'success');
        setSelectedFile(null);
        // Clear file input
        document.getElementById('file-upload-input').value = '';
        fetchUploads();
      } else {
        addToast(resData.error || 'Failed to ingest file.', 'error');
      }
    } catch (err) {
      addToast('Network error during upload process.', 'error');
    } finally {
      setUploading(false);
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'COMPLETED': return 'badge badge-completed';
      case 'FAILED': return 'badge badge-failed';
      case 'PARSING': return 'badge badge-pending';
      default: return 'badge badge-pending';
    }
  };

  return (
    <div>
      <div className="table-card" style={{ padding: '24px', marginBottom: '32px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Ingest ESG Dataset</h2>
        <form onSubmit={handleUploadSubmit}>
          <div className="upload-dropzone" onClick={() => document.getElementById('file-upload-input').click()}>
            <div className="upload-icon">📁</div>
            <div className="upload-title">
              {selectedFile ? `Selected: ${selectedFile.name}` : 'Click to select CSV data file'}
            </div>
            <div className="upload-subtitle">Only CSV datasets matching standard schemas are supported</div>
            <input 
              type="file" 
              id="file-upload-input" 
              accept=".csv" 
              style={{ display: 'none' }} 
              onChange={handleFileChange}
            />
          </div>
          
          <div className="upload-form-row">
            <div className="form-group" style={{ minWidth: '240px' }}>
              <label className="form-label">Data Source Standard Schema</label>
              <select 
                className="filter-select" 
                value={sourceType} 
                onChange={(e) => setSourceType(e.target.value)}
                style={{ width: '100%', height: '38px' }}
              >
                <option value="SAP_FUEL">SAP Fuel & Procurement Export</option>
                <option value="UTILITY_ELECTRICITY">Utility Portal Electricity Export</option>
                <option value="CORPORATE_TRAVEL">Corporate Booking Travel Log</option>
              </select>
            </div>
            
            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={uploading || !selectedFile}
              style={{ alignSelf: 'flex-end', height: '38px', minWidth: '140px' }}
            >
              {uploading ? 'Processing Ingest...' : 'Start Ingestion'}
            </button>
          </div>
        </form>
      </div>

      <div className="table-card">
        <div className="table-header-toolbar">
          <div className="toolbar-title">Ingestion History</div>
          <button className="btn btn-secondary btn-sm" onClick={fetchUploads}>🔄 Refresh</button>
        </div>
        
        {loading ? (
          <div style={{ padding: '40px', textAlignment: 'center', color: 'var(--text-secondary)' }}>
            Loading upload history...
          </div>
        ) : uploads.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            No uploads found for this tenant. Select a file above to begin ingestion.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>File Name</th>
                <th>Source Type</th>
                <th>Uploaded At</th>
                <th>Row Count</th>
                <th>Status</th>
                <th>Messages / Errors</th>
              </tr>
            </thead>
            <tbody>
              {uploads.map((upload) => (
                <tr key={upload.id}>
                  <td style={{ fontWeight: 500, color: 'var(--neutral-800)' }}>{upload.file_name}</td>
                  <td>{upload.source_type_display}</td>
                  <td>{upload.uploaded_at_formatted}</td>
                  <td>{upload.row_count} rows</td>
                  <td>
                    <span className={getStatusBadgeClass(upload.status)}>
                      {upload.status_display}
                    </span>
                  </td>
                  <td style={{ maxWidth: '300px', fontSize: '13px', color: upload.status === 'FAILED' ? 'var(--danger)' : 'var(--text-secondary)' }}>
                    {upload.error_message || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

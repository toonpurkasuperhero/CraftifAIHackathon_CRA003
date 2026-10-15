import { useEffect, useState } from 'react';
import { getHistory, deleteRecord, exportCSV } from '../services/api';
import AnimalTag, { SeverityTag, SourceTag } from '../components/AnimalTag';
import { formatTimestamp, formatConfidence, formatMs, SPECIES_KEYS, ANIMALS } from '../utils/animals';

const EMPTY = { animal: '', date_from: '', date_to: '', min_confidence: '', severity: '', source: '' };
const LABEL = { fontSize: 11, color: '#7a9cc0', fontWeight: 600, letterSpacing: 0.5, display: 'block', marginBottom: 6 };

function toParams(f) {
    const p = {};
    if (f.animal) p.animal = f.animal;
    if (f.date_from) p.date_from = f.date_from;
    if (f.date_to) p.date_to = f.date_to;
    if (f.min_confidence) p.min_confidence = parseFloat(f.min_confidence) / 100;
    if (f.severity) p.severity = f.severity;
    if (f.source) p.source = f.source;
    return p;
}

export default function History() {
    const [records, setRecords] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState(EMPTY);
    const [deleting, setDeleting] = useState(null);

    const fetchHistory = async (f = filters) => {
        setLoading(true);
        try {
            const res = await getHistory(toParams(f));
            setRecords(res.data.records || []);
        } catch { setRecords([]); }
        finally { setLoading(false); }
    };

    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => { fetchHistory(); }, []);

    const handleDelete = async (id) => {
        setDeleting(id);
        try { await deleteRecord(id); setRecords(r => r.filter(x => x.id !== id)); } catch { /* keep row */ }
        finally { setDeleting(null); }
    };

    const set = (k) => (e) => setFilters(f => ({ ...f, [k]: e.target.value }));
    const headers = ['#', 'Time', 'Species', 'Conf', 'Severity', 'Sensor', 'Zone', 'Track', 'ESP32 ACK', 'E2E', 'On-board', 'Source', ''];

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1>📋 <span className="gradient-text">Event History</span></h1>
                <p>Every perception event and the roadside unit's response, with measured latency</p>
            </div>

            <div className="glass-card" style={{ padding: '18px 20px', marginBottom: 20 }}>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                    <div style={{ flex: '1 1 140px' }}>
                        <label style={LABEL}>SPECIES</label>
                        <select className="form-select" style={{ width: '100%' }} value={filters.animal} onChange={set('animal')}>
                            <option value="">All species</option>
                            {SPECIES_KEYS.map(a => <option key={a} value={a}>{ANIMALS[a].label}</option>)}
                        </select>
                    </div>
                    <div style={{ flex: '1 1 120px' }}>
                        <label style={LABEL}>SEVERITY</label>
                        <select className="form-select" style={{ width: '100%' }} value={filters.severity} onChange={set('severity')}>
                            <option value="">All</option>
                            {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'WARN'].map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                    </div>
                    <div style={{ flex: '1 1 120px' }}>
                        <label style={LABEL}>SOURCE</label>
                        <select className="form-select" style={{ width: '100%' }} value={filters.source} onChange={set('source')}>
                            <option value="">All</option>
                            <option value="pipegen">PipeGen (live)</option>
                            <option value="synthetic">Test / synthetic</option>
                            <option value="replay">Rehearsal replay</option>
                            <option value="webcam">Legacy webcam</option>
                            <option value="image">Legacy image</option>
                        </select>
                    </div>
                    <div style={{ flex: '1 1 130px' }}>
                        <label style={LABEL}>FROM DATE</label>
                        <input type="date" className="form-input" value={filters.date_from} onChange={set('date_from')} />
                    </div>
                    <div style={{ flex: '1 1 130px' }}>
                        <label style={LABEL}>TO DATE</label>
                        <input type="date" className="form-input" value={filters.date_to} onChange={set('date_to')} />
                    </div>
                    <div style={{ flex: '1 1 110px' }}>
                        <label style={LABEL}>MIN CONF %</label>
                        <input type="number" className="form-input" min={0} max={100} placeholder="e.g. 60"
                            value={filters.min_confidence} onChange={set('min_confidence')} />
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn-primary" onClick={() => fetchHistory()} style={{ whiteSpace: 'nowrap' }}>🔍 Apply</button>
                        <button className="btn-secondary" onClick={() => { setFilters(EMPTY); fetchHistory(EMPTY); }} style={{ whiteSpace: 'nowrap' }}>✕ Clear</button>
                    </div>
                </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#7a9cc0' }}>
                    {loading ? 'Loading…' : `${records.length} event${records.length !== 1 ? 's' : ''}`}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn-secondary" onClick={() => exportCSV(toParams(filters))} style={{ fontSize: 12, padding: '6px 14px' }}>📥 Export CSV</button>
                    <button className="btn-secondary" onClick={() => fetchHistory()} style={{ fontSize: 12, padding: '6px 14px' }}>🔄 Refresh</button>
                </div>
            </div>

            <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                    <table className="data-table">
                        <thead><tr>{headers.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
                        <tbody>
                            {loading ? (
                                <tr><td colSpan={headers.length} className="empty">Loading events…</td></tr>
                            ) : records.length === 0 ? (
                                <tr><td colSpan={headers.length} className="empty">No events found.</td></tr>
                            ) : records.map((r) => (
                                <tr key={r.id}>
                                    <td style={{ color: '#4a6a8a' }}>{r.id}</td>
                                    <td style={{ whiteSpace: 'nowrap' }}>{formatTimestamp(r.timestamp)}</td>
                                    <td><AnimalTag animal={r.animal} /></td>
                                    <td style={{ fontWeight: 700, color: r.confidence >= 0.7 ? '#00ff88' : '#ffd60a' }}>{formatConfidence(r.confidence)}</td>
                                    <td><SeverityTag severity={r.severity} /></td>
                                    <td>{r.sensor_confirmed == null ? '—' : r.sensor_confirmed ? '📡 yes' : 'no'}</td>
                                    <td>{r.in_road_zone == null ? '—' : r.in_road_zone ? 'road' : 'verge'}</td>
                                    <td>{r.track_id != null && r.track_id >= 0 ? `#${r.track_id}` : '—'}</td>
                                    <td style={{ fontWeight: 700, color: r.ack_state === 'TIMEOUT' ? '#ff3b6b' : r.ack_state === 'IGNORED' ? '#7a9cc0' : '#00ff88' }}>
                                        {r.ack_state || (r.event_id ? 'pending' : '—')}
                                    </td>
                                    <td>{formatMs(r.latency_ms)}</td>
                                    <td>{formatMs(r.onboard_ms)}</td>
                                    <td><SourceTag source={r.source} /></td>
                                    <td>
                                        <button onClick={() => handleDelete(r.id)} disabled={deleting === r.id} aria-label="Delete" style={{
                                            background: 'rgba(255,59,107,0.1)', border: '1px solid rgba(255,59,107,0.3)',
                                            color: '#ff3b6b', borderRadius: 6, padding: '4px 10px', fontSize: 11, cursor: 'pointer',
                                            opacity: deleting === r.id ? 0.5 : 1,
                                        }}>{deleting === r.id ? '…' : '🗑'}</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

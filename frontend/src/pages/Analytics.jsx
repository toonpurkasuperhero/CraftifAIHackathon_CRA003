import { useEffect, useState } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, AreaChart, Area, Legend,
} from 'recharts';
import CustomTooltip from '../components/ChartTooltip';
import { getAnalytics, getLatency, getPipelineInfo, exportCSV, downloadEvidence } from '../services/api';
import { ANIMALS, CHART_COLORS, SEVERITY, formatAnimalName, formatMs } from '../utils/animals';

function InsightCard({ icon, title, value, sub, color }) {
    return (
        <div className="glass-card" style={{ padding: '18px 20px', borderLeft: `3px solid ${color}` }}>
            <div style={{ fontSize: 22, marginBottom: 8 }}>{icon}</div>
            <div style={{ fontSize: 11, color: '#7a9cc0', fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 4 }}>{title}</div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#e8f4fd', marginBottom: 4 }}>{value ?? '—'}</div>
            {sub && <div style={{ fontSize: 11, color: '#4a6a8a' }}>{sub}</div>}
        </div>
    );
}

const Empty = ({ h = 200, children }) => (
    <div className="empty" style={{ height: h, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{children}</div>
);

export default function Analytics() {
    const [data, setData] = useState(null);
    const [lat, setLat] = useState(null);
    const [realOnly, setRealOnly] = useState(false);
    const [pipe, setPipe] = useState(null);

    useEffect(() => {
        const load = async () => {
            try {
                const [a, l] = await Promise.all([getAnalytics(), getLatency(!realOnly)]);
                setData(a.data);
                setLat(l.data);
            } catch { /* backend offline */ }
        };
        load();
        const t = setInterval(load, 10000);
        return () => clearInterval(t);
    }, [realOnly]);

    useEffect(() => { getPipelineInfo().then(r => setPipe(r.data)).catch(() => setPipe(null)); }, []);

    const animalData = Object.entries(data?.animal_counts || {}).map(([k, v], i) => ({
        name: formatAnimalName(k), events: v, fill: ANIMALS[k]?.color || CHART_COLORS[i % CHART_COLORS.length],
    }));
    const sevData = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'WARN'].map(s => ({
        name: s, alerts: data?.severities?.[s] || 0, fill: SEVERITY[s].color,
    }));
    const hourlyData = Object.entries(data?.hourly || {}).map(([h, v]) => ({ hour: `${h.padStart(2, '0')}h`, count: v }));
    const histData = lat?.histogram?.map(h => ({ bucket: `${h.bucket} ms`, events: h.count })) || [];
    const precisions = (pipe?.precisions || []).filter(p => p.fps != null || p.map50 != null);
    const confirmed = data?.sensor_confirmation?.confirmed || 0;
    const unconfirmed = data?.sensor_confirmation?.unconfirmed || 0;
    const fusedShare = confirmed + unconfirmed ? `${Math.round((confirmed / (confirmed + unconfirmed)) * 100)}%` : '—';

    return (
        <div className="animate-in">
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                <div>
                    <h1>📊 <span className="gradient-text">Analytics & Evidence</span></h1>
                    <p>Loop latency, response severity, species activity and the PipeGen precision trade-off</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn-secondary" onClick={() => exportCSV({})} style={{ fontSize: 12, padding: '8px 16px' }}>📥 Export CSV</button>
                    <button className="btn-primary" onClick={downloadEvidence} style={{ fontSize: 12, padding: '8px 16px' }}>📦 Evidence pack</button>
                </div>
            </div>

            <div className="grid-4" style={{ marginBottom: 24 }}>
                <InsightCard icon="⏱" title="Capture → ACK p50 / p95" color="#00ff88"
                    value={lat?.acked ? `${formatMs(lat.e2e_ms.p50)} / ${formatMs(lat.e2e_ms.p95)}` : '—'}
                    sub={`${lat?.acked || 0} actuated events ${realOnly ? '(real PipeGen only)' : '(incl. tests and rehearsal)'}`} />
                <InsightCard icon="⚙️" title="On-board RX → actuate (max)" color="#ffd60a"
                    value={formatMs(lat?.onboard_ms?.max)} sub="PRD target ≤ 100 ms (WG-ACT-03)" />
                <InsightCard icon="✅" title="ACK rate" color="#00b4ff"
                    value={lat?.ack_rate != null ? `${Math.round(lat.ack_rate * 100)}%` : '—'}
                    sub={`${lat?.timeouts || 0} timeouts of ${lat?.events || 0} events`} />
                <InsightCard icon="📡" title="Sensor-confirmed share" color="#7c3aed"
                    value={fusedShare} sub={`${confirmed} confirmed · ${unconfirmed} camera-only`} />
            </div>

            <div className="grid-2" style={{ marginBottom: 16 }}>
                <div className="glass-card" style={{ padding: '20px 24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
                        <div className="section-title" style={{ margin: 0 }}>⏱ End-to-end latency histogram</div>
                        <label style={{ marginLeft: 'auto', fontSize: 12, color: '#7a9cc0', display: 'flex', gap: 6, alignItems: 'center' }}>
                            <input type="checkbox" checked={realOnly} onChange={e => setRealOnly(e.target.checked)} style={{ accentColor: '#00ff88' }} />
                            Real PipeGen events only
                        </label>
                    </div>
                    {!lat?.acked ? <Empty>No ACKed events yet.</Empty> : (
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={histData} margin={{ left: -10 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e3050" />
                                <XAxis dataKey="bucket" tick={{ fill: '#7a9cc0', fontSize: 10 }} />
                                <YAxis tick={{ fill: '#7a9cc0', fontSize: 10 }} allowDecimals={false} />
                                <Tooltip content={<CustomTooltip />} />
                                <Bar dataKey="events" name="Events" fill="#00ff88" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </div>

                <div className="glass-card" style={{ padding: '20px 24px' }}>
                    <div className="section-title">🚨 Response severity (from ESP32 ACKs)</div>
                    {!Object.keys(data?.severities || {}).length ? <Empty>No actuated alerts yet.</Empty> : (
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={sevData} margin={{ left: -10 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e3050" />
                                <XAxis dataKey="name" tick={{ fill: '#7a9cc0', fontSize: 11 }} />
                                <YAxis tick={{ fill: '#7a9cc0', fontSize: 10 }} allowDecimals={false} />
                                <Tooltip content={<CustomTooltip />} />
                                <Bar dataKey="alerts" name="Alerts" radius={[4, 4, 0, 0]}>
                                    {sevData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>

            <div className="glass-card" style={{ padding: '20px 24px', marginBottom: 16 }}>
                <div className="section-title">🧮 PipeGen precision trade-off (FP32 · FP16 · INT8)</div>
                {!precisions.length ? (
                    <div className="muted">
                        Copy the numbers from PipeGen's Compiler-stage speed report into
                        {' '}<code>perception/reports/pipeline_info.json</code> (template: <code>pipeline_info.example.json</code>).
                        This chart then shows FPS and mAP per precision for the Edge Optimization bonus.
                    </div>
                ) : (
                    <div className="grid-2">
                        <ResponsiveContainer width="100%" height={220}>
                            <BarChart data={precisions} margin={{ left: -10 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e3050" />
                                <XAxis dataKey="precision" tick={{ fill: '#7a9cc0', fontSize: 11 }} />
                                <YAxis tick={{ fill: '#7a9cc0', fontSize: 10 }} />
                                <Tooltip content={<CustomTooltip />} />
                                <Legend />
                                <Bar dataKey="fps" name="FPS" fill="#00b4ff" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                        <ResponsiveContainer width="100%" height={220}>
                            <BarChart data={precisions} margin={{ left: -10 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e3050" />
                                <XAxis dataKey="precision" tick={{ fill: '#7a9cc0', fontSize: 11 }} />
                                <YAxis tick={{ fill: '#7a9cc0', fontSize: 10 }} domain={[0, 1]} />
                                <Tooltip content={<CustomTooltip />} />
                                <Legend />
                                <Bar dataKey="map50" name="mAP50" fill="#00ff88" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="map50_95" name="mAP50-95" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </div>

            <div className="grid-2">
                <div className="glass-card" style={{ padding: '20px 24px' }}>
                    <div className="section-title">🦁 Events per species</div>
                    {!animalData.length ? <Empty>No data yet.</Empty> : (
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={animalData} layout="vertical" margin={{ left: 20 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e3050" />
                                <XAxis type="number" tick={{ fill: '#7a9cc0', fontSize: 11 }} allowDecimals={false} />
                                <YAxis type="category" dataKey="name" tick={{ fill: '#7a9cc0', fontSize: 11 }} width={100} />
                                <Tooltip content={<CustomTooltip />} />
                                <Bar dataKey="events" name="Events" radius={[0, 4, 4, 0]}>
                                    {animalData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </div>
                <div className="glass-card" style={{ padding: '20px 24px' }}>
                    <div className="section-title">⏰ 24-hour activity</div>
                    <ResponsiveContainer width="100%" height={200}>
                        <AreaChart data={hourlyData} margin={{ left: -10 }}>
                            <defs>
                                <linearGradient id="grad1" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#00ff88" stopOpacity={0.4} />
                                    <stop offset="95%" stopColor="#00ff88" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e3050" />
                            <XAxis dataKey="hour" tick={{ fill: '#7a9cc0', fontSize: 9 }} interval={3} />
                            <YAxis tick={{ fill: '#7a9cc0', fontSize: 10 }} allowDecimals={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Area type="monotone" dataKey="count" name="Events" stroke="#00ff88" fill="url(#grad1)" strokeWidth={2} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
}

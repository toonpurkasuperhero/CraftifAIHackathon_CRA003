import { useEffect, useState } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, LineChart, Line, CartesianGrid,
} from 'recharts';
import StatCard from '../components/StatCard';
import AnimalTag, { SeverityTag, SourceTag } from '../components/AnimalTag';
import LoopStatusStrip from '../components/LoopStatusStrip';
import CustomTooltip from '../components/ChartTooltip';
import { getAnalytics, getHistory, getLatency } from '../services/api';
import { useLive } from '../live/LiveContext';
import { ANIMALS, CHART_COLORS, formatAnimalName, formatTimestamp, formatMs } from '../utils/animals';

export default function Dashboard() {
    const { feed } = useLive();
    const [analytics, setAnalytics] = useState(null);
    const [recent, setRecent] = useState([]);
    const [latency, setLatency] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchData = async () => {
        try {
            const [aRes, hRes, lRes] = await Promise.all([getAnalytics(), getHistory({ limit: 8 }), getLatency(false)]);
            setAnalytics(aRes.data);
            setRecent(hRes.data.records || []);
            if (lRes.data.acked) setLatency({ ...lRes.data, real: true });
            else setLatency({ ...(await getLatency(true)).data, real: false });  // fall back, clearly labelled
        } catch { /* backend may not be running yet */ }
        finally { setLoading(false); }
    };

    // Poll slowly, and refresh immediately whenever a new event or ACK arrives over the WebSocket.
    const feedKey = feed.length ? `${feed[0].event_id}-${feed[0].ack ? 1 : 0}` : '';
    useEffect(() => { fetchData(); const t = setInterval(fetchData, 15000); return () => clearInterval(t); }, []);
    useEffect(() => { if (feedKey) fetchData(); }, [feedKey]);

    const animalChartData = Object.entries(analytics?.animal_counts || {}).map(([k, v]) => ({
        name: formatAnimalName(k), value: v, animal: k,
    }));
    const hourlyData = Object.entries(analytics?.hourly || {})
        .map(([h, v]) => ({ hour: `${h}:00`, count: v }))
        .filter((_, i) => i % 2 === 0);
    const dailyData = Object.entries(analytics?.daily || {}).map(([d, v]) => ({ date: d.slice(5), count: v }));
    const alerts = (analytics?.severities?.CRITICAL || 0) + (analytics?.severities?.HIGH || 0);

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1>🌿 <span className="gradient-text">Mission Control</span></h1>
                <p>Camera sees (PipeGen) · roadside unit acts (FirmGen ESP32) · every alert measured end to end</p>
            </div>

            <LoopStatusStrip />

            <div className="grid-4" style={{ marginBottom: 28 }}>
                <StatCard icon="🐾" label="Events (all time)" value={analytics?.total ?? '—'}
                    sub={`${analytics?.today ?? 0} today`} loading={loading} accent="rgba(0,255,136,0.08)" />
                <StatCard icon="🚨" label="High / critical alerts" value={alerts}
                    sub="Severity reported by the ESP32" loading={loading} accent="rgba(255,59,107,0.08)" />
                <StatCard icon="⏱" label="Capture → ACK p50" value={formatMs(latency?.e2e_ms?.p50)}
                    sub={latency?.acked ? `p95 ${formatMs(latency.e2e_ms.p95)} · ${latency.acked} ${latency.real ? 'real PipeGen events' : 'test/rehearsal events'}` : 'No ACKed events yet'}
                    loading={loading} accent="rgba(0,180,255,0.08)" />
                <StatCard icon="🏆" label="Most frequent"
                    value={analytics?.most_frequent ? `${ANIMALS[analytics.most_frequent]?.icon || ''} ${formatAnimalName(analytics.most_frequent)}` : '—'}
                    sub="5 road-vulnerable species tracked" loading={loading} accent="rgba(124,58,237,0.08)" />
            </div>

            <div className="grid-2" style={{ marginBottom: 20 }}>
                <div className="glass-card" style={{ padding: '20px 24px' }}>
                    <div className="section-title">📊 Detections per species</div>
                    {animalChartData.length === 0 ? (
                        <div className="empty" style={{ height: 180 }}>No events yet. Start the PipeGen pipeline or fire a test alert.</div>
                    ) : (
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={animalChartData} margin={{ left: -10 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e3050" />
                                <XAxis dataKey="name" tick={{ fill: '#7a9cc0', fontSize: 11 }} />
                                <YAxis tick={{ fill: '#7a9cc0', fontSize: 11 }} allowDecimals={false} />
                                <Tooltip content={<CustomTooltip />} />
                                <Bar isAnimationActive={false} dataKey="value" name="Events" radius={[4, 4, 0, 0]}>
                                    {animalChartData.map((entry, i) => (
                                        <Cell key={i} fill={ANIMALS[entry.animal]?.color || CHART_COLORS[i % CHART_COLORS.length]} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </div>

                <div className="glass-card" style={{ padding: '20px 24px' }}>
                    <div className="section-title">🥧 Species distribution</div>
                    {animalChartData.length === 0 ? (
                        <div className="empty" style={{ height: 200 }}>No data yet.</div>
                    ) : (
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie isAnimationActive={false} data={animalChartData} cx="50%" cy="52%" outerRadius={70} dataKey="value"
                                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                    labelLine={false} style={{ fontSize: 11 }}>
                                    {animalChartData.map((d, i) => <Cell key={i} fill={ANIMALS[d.animal]?.color || CHART_COLORS[i % CHART_COLORS.length]} />)}
                                </Pie>
                                <Tooltip content={<CustomTooltip />} />
                            </PieChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>

            <div className="grid-2" style={{ marginBottom: 20 }}>
                <div className="glass-card" style={{ padding: '20px 24px' }}>
                    <div className="section-title">⏰ Hourly activity</div>
                    <ResponsiveContainer width="100%" height={180}>
                        <LineChart data={hourlyData} margin={{ left: -10 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e3050" />
                            <XAxis dataKey="hour" tick={{ fill: '#7a9cc0', fontSize: 10 }} />
                            <YAxis tick={{ fill: '#7a9cc0', fontSize: 10 }} allowDecimals={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Line isAnimationActive={false} type="monotone" dataKey="count" name="Events" stroke="#00ff88" strokeWidth={2} dot={{ fill: '#00ff88', r: 3 }} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
                <div className="glass-card" style={{ padding: '20px 24px' }}>
                    <div className="section-title">📅 Daily trend</div>
                    <ResponsiveContainer width="100%" height={180}>
                        <BarChart data={dailyData} margin={{ left: -10 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e3050" />
                            <XAxis dataKey="date" tick={{ fill: '#7a9cc0', fontSize: 10 }} />
                            <YAxis tick={{ fill: '#7a9cc0', fontSize: 10 }} allowDecimals={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Bar isAnimationActive={false} dataKey="count" name="Events" fill="#00b4ff" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="glass-card" style={{ padding: '20px 24px' }}>
                <div className="section-title">🕒 Recent events</div>
                {recent.length === 0 ? (
                    <div className="empty">No events recorded yet.</div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {recent.map(r => (
                            <div key={r.id} style={{
                                display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', flexWrap: 'wrap',
                                background: '#080e1c', borderRadius: 10, border: '1px solid #1e3050',
                            }}>
                                <AnimalTag animal={r.animal} />
                                <SeverityTag severity={r.severity} />
                                <span style={{ fontSize: 13, color: '#00ff88', fontWeight: 700 }}>
                                    {(r.confidence * 100).toFixed(1)}%
                                </span>
                                {r.sensor_confirmed && <span style={{ fontSize: 11, color: '#ffd60a' }}>📡 sensor-confirmed</span>}
                                <span style={{ fontSize: 12, color: r.ack_state === 'TIMEOUT' ? '#ff3b6b' : '#7a9cc0' }}>
                                    {r.ack_state ? `${r.ack_state} · ${formatMs(r.latency_ms)}` : r.event_id ? 'awaiting ACK' : ''}
                                </span>
                                <span style={{ fontSize: 12, color: '#4a6a8a', marginLeft: 'auto' }}>{formatTimestamp(r.timestamp)}</span>
                                <SourceTag source={r.source} />
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

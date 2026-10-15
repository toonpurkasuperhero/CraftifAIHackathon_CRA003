import { useEffect, useState } from 'react';
import { useLoopStatus } from '../live/LiveContext';
import { downloadEvidence, getSpecies, sendCommand, setMode, testAlert } from '../services/api';
import AnimalTag, { SeverityTag } from '../components/AnimalTag';
import LoopStatusStrip from '../components/LoopStatusStrip';
import { ANIMALS, SPECIES_KEYS, formatMs } from '../utils/animals';

export default function Control() {
    const s = useLoopStatus();
    const [species, setSpecies] = useState([]);
    const [conf, setConf] = useState(0.9);
    const [busy, setBusy] = useState(null);
    const [msg, setMsg] = useState(null);

    useEffect(() => { getSpecies().then(r => setSpecies(r.data)).catch(() => {}); }, []);

    const run = async (key, fn, ok) => {
        setBusy(key);
        setMsg(null);
        try {
            await fn();
            setMsg({ ok: true, text: ok });
        } catch (e) {
            setMsg({ ok: false, text: e?.response?.data?.detail || 'Request failed (is the broker up?)' });
        } finally {
            setBusy(null);
        }
    };

    const armed = s.mode !== 'disarmed';

    return (
        <div className="animate-in">
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                <div>
                    <h1>🎛 <span className="gradient-text">Control & Test</span></h1>
                    <p>Drive the roadside unit over MQTT and prove each path independently of the camera</p>
                </div>
                <button className="btn-primary" onClick={downloadEvidence}>📦 Download evidence pack</button>
            </div>

            <LoopStatusStrip />

            {msg && (
                <div style={{ marginBottom: 16, padding: '10px 16px', borderRadius: 10, fontSize: 13,
                    background: msg.ok ? 'rgba(0,255,136,0.08)' : 'rgba(255,59,107,0.1)',
                    color: msg.ok ? '#00ff88' : '#ff3b6b', border: `1px solid ${msg.ok ? 'rgba(0,255,136,0.3)' : 'rgba(255,59,107,0.3)'}` }}>
                    {msg.text}
                </div>
            )}

            <div className="grid-3" style={{ marginBottom: 20 }}>
                <div className="glass-card" style={{ padding: '18px 20px' }}>
                    <div className="section-title">🛑 Actuation mode</div>
                    <button className={`kill-switch ${armed ? '' : 'armed'}`} disabled={busy === 'mode'}
                        onClick={() => run('mode', () => setMode(armed ? 'disarmed' : 'armed'),
                            armed ? 'Disarm published: the ESP32 will ACK events as IGNORED' : 'Armed: actuation enabled')}>
                        {armed ? 'DISARM (kill switch)' : 'ARM roadside unit'}
                    </button>
                    <div className="muted" style={{ marginTop: 10 }}>
                        Retained on <code>wildguard/control/mode</code>, so the board picks it up again after a reboot.
                        Current: <strong style={{ color: armed ? '#00ff88' : '#ff3b6b' }}>{(s.mode || 'unknown').toUpperCase()}</strong>
                    </div>
                </div>

                <div className="glass-card" style={{ padding: '18px 20px' }}>
                    <div className="section-title">🧪 Board tests</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <button className="btn-secondary" disabled={!!busy}
                            onClick={() => run('trip', () => sendCommand('sim_trip', 5), 'Sensor trip simulated for 5 s: watch the node go ARMED (amber)')}>
                            📡 Simulate sensor trip (5 s)
                        </button>
                        <button className="btn-secondary" disabled={!!busy}
                            onClick={() => run('self', () => sendCommand('selftest'), 'Self-test started: the board cycles every species profile')}>
                            💡 Run LED / buzzer self-test
                        </button>
                    </div>
                    <div className="muted" style={{ marginTop: 10 }}>
                        One-shot commands on <code>wildguard/control/cmd</code> (not retained).
                    </div>
                </div>

                <div className="glass-card" style={{ padding: '18px 20px' }}>
                    <div className="section-title">📈 Loop counters</div>
                    {[
                        ['Events seen', s.counters.detections ?? 0],
                        ['ACKs received', s.counters.acks ?? 0],
                        ['ACK timeouts', s.counters.timeouts ?? 0],
                        ['Last ACK latency', formatMs(s.lastAck?.latency_ms)],
                    ].map(([k, v]) => (
                        <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #1e3050', fontSize: 13 }}>
                            <span style={{ color: '#7a9cc0' }}>{k}</span><strong>{v}</strong>
                        </div>
                    ))}
                </div>
            </div>

            <div className="glass-card" style={{ padding: '18px 20px', marginBottom: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 14 }}>
                    <div className="section-title" style={{ margin: 0 }}>🐾 Simulate a perception event</div>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#7a9cc0', marginLeft: 'auto' }}>
                        Confidence {(conf * 100).toFixed(0)}%
                        <input type="range" min={0.1} max={1} step={0.05} value={conf} onChange={e => setConf(parseFloat(e.target.value))} />
                    </label>
                </div>
                <div className="muted" style={{ marginBottom: 12 }}>
                    Publishes a contract-v1 event marked <code>synthetic</code> on the same topic PipeGen's bridge uses.
                    It is stored as a test event and excluded from the "real" latency figures.
                    Below the 50 % threshold the board must reply IGNORED.
                </div>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {SPECIES_KEYS.map(k => (
                        <button key={k} className="btn-secondary" disabled={!!busy}
                            onClick={() => run(k, () => testAlert(k, conf), `Synthetic ${ANIMALS[k].label} published`)}>
                            {ANIMALS[k].icon} {ANIMALS[k].label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="grid-2">
                <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
                    <div className="section-title" style={{ padding: '16px 20px 0' }}>🔁 Last 10 ACKs from the ESP32</div>
                    <div style={{ overflowX: 'auto' }}>
                        <table className="data-table">
                            <thead><tr>{['Event', 'Profile', 'State', 'Severity', 'Sensor', 'E2E', 'On-board'].map(h => <th key={h}>{h}</th>)}</tr></thead>
                            <tbody>
                                {s.recentAcks.length === 0 ? (
                                    <tr><td colSpan={7} className="empty">No ACKs yet</td></tr>
                                ) : s.recentAcks.map((a, i) => (
                                    <tr key={`${a.event_id}-${i}`}>
                                        <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{a.event_id}</td>
                                        <td>{a.profile ? <AnimalTag animal={a.profile} /> : '—'}</td>
                                        <td style={{ color: a.state === 'IGNORED' ? '#7a9cc0' : '#00ff88', fontWeight: 700 }}>
                                            {a.state}{a.reason ? ` (${a.reason})` : ''}
                                        </td>
                                        <td><SeverityTag severity={a.severity} /></td>
                                        <td>{a.confirmed == null ? '—' : a.confirmed ? '✓' : '✗'}</td>
                                        <td>{formatMs(a.latency_ms)}</td>
                                        <td>{formatMs(a.onboard_ms)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
                    <div className="section-title" style={{ padding: '16px 20px 0' }}>📋 Species → response profiles (PRD WG-EVT-04/05)</div>
                    <div style={{ overflowX: 'auto' }}>
                        <table className="data-table">
                            <thead><tr>{['Species', 'IUCN', 'Unconfirmed', 'Sensor-confirmed', 'LED', 'Buzzer'].map(h => <th key={h}>{h}</th>)}</tr></thead>
                            <tbody>
                                {species.map(r => (
                                    <tr key={r.class}>
                                        <td><AnimalTag animal={r.class} /></td>
                                        <td>{r.iucn}</td>
                                        <td><SeverityTag severity={r.unconfirmed_severity} /></td>
                                        <td><SeverityTag severity={r.confirmed_severity} /></td>
                                        <td>{r.led}</td>
                                        <td>{r.buzzer}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}

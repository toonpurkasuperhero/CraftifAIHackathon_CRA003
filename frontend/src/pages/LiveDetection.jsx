import { useLive, useLoopStatus } from '../live/LiveContext';
import { STREAM_URL } from '../services/api';
import AnimalTag, { SeverityTag } from '../components/AnimalTag';
import LoopStatusStrip from '../components/LoopStatusStrip';
import LoopTimeline from '../components/LoopTimeline';
import { formatAgo, formatMs } from '../utils/animals';

const STATE_STYLE = {
    IDLE: { color: '#00ff88', label: 'IDLE · green' },
    ARMED: { color: '#ffd60a', label: 'ARMED · amber' },
    ALERT: { color: '#ff3b6b', label: 'ALERT · red strobe' },
    DEGRADED: { color: '#ffb300', label: 'DEGRADED · sensor-only amber' },
    DISARMED: { color: '#7a9cc0', label: 'DISARMED' },
    TEST: { color: '#00b4ff', label: 'SELF-TEST' },
    FAULT: { color: '#ff3b6b', label: 'FAULT' },
    BOOT: { color: '#7a9cc0', label: 'BOOT' },
};

function SensorPanel() {
    const s = useLoopStatus();
    const sensor = s.sensor;
    const threshold = sensor?.threshold_cm ?? 20;
    const d = sensor?.distance_cm;
    const st = STATE_STYLE[sensor?.state] || { color: '#4a6a8a', label: sensor?.state || 'NO DATA' };
    const distColor = d == null ? '#4a6a8a' : d < threshold ? '#ff3b6b' : d < threshold * 2.5 ? '#ffb300' : '#00ff88';
    return (
        <div className="glass-card" style={{ padding: '18px 20px', border: sensor?.armed ? '1px solid rgba(255,214,10,0.5)' : undefined }}>
            <div style={{ fontWeight: 700, marginBottom: 14, fontSize: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                📡 Roadside unit (ESP32)
                <span style={{
                    marginLeft: 'auto', fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
                    background: s.nodeOnline ? 'rgba(0,255,136,0.1)' : 'rgba(255,59,107,0.12)',
                    color: s.nodeOnline ? '#00ff88' : '#ff3b6b',
                }}>{s.nodeOnline ? '● LIVE' : '⚠ OFFLINE'}</span>
            </div>

            <div style={{ padding: '10px 14px', borderRadius: 10, marginBottom: 14, textAlign: 'center',
                background: 'rgba(0,0,0,0.25)', border: `1px solid ${st.color}` }}>
                <div style={{ fontSize: 11, color: '#4a6a8a', letterSpacing: 1 }}>STATE MACHINE</div>
                <div style={{ fontSize: 18, fontWeight: 800, color: st.color }}>{st.label}</div>
            </div>

            <div style={{ fontSize: 11, color: '#4a6a8a', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>
                Ultrasonic distance (HC-SR04)
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <span style={{ fontSize: 32, fontWeight: 800, color: distColor, lineHeight: 1 }}>{d != null ? d.toFixed(1) : '—'}</span>
                <span style={{ fontSize: 14, color: '#4a6a8a' }}>cm</span>
            </div>
            <div style={{ marginTop: 8, height: 6, background: '#1e3050', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{
                    height: '100%', borderRadius: 3, width: d != null ? `${Math.min((d / 250) * 100, 100)}%` : '0%',
                    background: d != null && d < threshold ? '#ff3b6b' : 'linear-gradient(90deg, #00ff88, #00b4ff)',
                    transition: 'width 0.4s ease',
                }} />
            </div>
            <div style={{ marginTop: 4, fontSize: 10, color: '#4a6a8a', display: 'flex', justifyContent: 'space-between' }}>
                <span>0</span><span style={{ color: '#ffb300' }}>ARM below {threshold} cm</span><span>250 cm</span>
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
                {[
                    ['PIR', sensor?.pir ? 'MOTION' : 'clear', sensor?.pir],
                    ['ARMED', sensor?.armed ? 'YES' : 'no', sensor?.armed],
                    ['MODE', (s.mode || sensor?.mode || '—').toUpperCase(), s.mode === 'disarmed'],
                ].map(([k, v, hot]) => (
                    <div key={k} style={{
                        flex: 1, padding: '6px 10px', borderRadius: 10, textAlign: 'center',
                        background: hot ? 'rgba(255,214,10,0.12)' : 'rgba(0,255,136,0.06)',
                        border: `1px solid ${hot ? 'rgba(255,214,10,0.4)' : 'rgba(0,255,136,0.2)'}`,
                    }}>
                        <div style={{ fontSize: 9, color: '#4a6a8a', letterSpacing: 1 }}>{k}</div>
                        <div style={{ fontSize: 12, fontWeight: 800, color: hot ? '#ffd60a' : '#00ff88' }}>{v}</div>
                    </div>
                ))}
            </div>
            <div className="muted" style={{ marginTop: 10 }}>
                Sensor arming upgrades a camera detection by one severity level (two modalities agree → fewer false alarms).
            </div>
        </div>
    );
}

function TelemetryPanel() {
    const { telemetry, node, now } = useLoopStatus();
    const rows = telemetry ? [
        ['Uptime', telemetry.uptime_s != null ? `${telemetry.uptime_s} s` : '—'],
        ['Free heap', telemetry.heap_free != null ? `${(telemetry.heap_free / 1024).toFixed(1)} KB` : '—'],
        ['Min heap', telemetry.heap_min != null ? `${(telemetry.heap_min / 1024).toFixed(1)} KB` : '—'],
        ['RSSI', telemetry.rssi != null ? `${telemetry.rssi} dBm` : '—'],
        ['Events RX', telemetry.rx ?? '—'],
        ['Actions', telemetry.actions ?? '—'],
        ['Ignored', telemetry.ignored ?? '—'],
        ['Malformed', telemetry.malformed ?? '—'],
    ] : [];
    return (
        <div className="glass-card" style={{ padding: '16px 20px' }}>
            <div style={{ fontWeight: 700, marginBottom: 10, fontSize: 14 }}>🧠 Board internals</div>
            <div className="muted" style={{ marginBottom: 10 }}>
                From the firmware telemetry topic · fw {node.fw || '—'} · {formatAgo(node.last_seen_ms, now)}
            </div>
            {!telemetry ? <div className="empty">No telemetry yet</div> : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                    {rows.map(([k, v]) => (
                        <div key={k} style={{ background: '#080e1c', borderRadius: 8, padding: '6px 10px', border: '1px solid #1e3050' }}>
                            <div style={{ fontSize: 9, color: '#4a6a8a', letterSpacing: 1, textTransform: 'uppercase' }}>{k}</div>
                            <div style={{ fontSize: 13, fontWeight: 700, color: '#e8f4fd' }}>{v}</div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function StreamPanel() {
    const { pipelineAlive, pipelineFps, pipelineSimulated, streamUrl } = useLoopStatus();
    const url = STREAM_URL || streamUrl;
    const mjpeg = url && /mjpe?g/i.test(url);
    return (
        <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid #1e3050' }}>
                <div className={`status-dot ${pipelineAlive ? 'active' : 'inactive'}`} />
                <span style={{ fontSize: 12, fontWeight: 700, color: pipelineAlive ? '#00ff88' : '#4a6a8a' }}>
                    {pipelineAlive ? `PIPEGEN LIVE · ${pipelineFps ?? '—'} FPS` : 'PIPEGEN: NO MESSAGES'}
                </span>
                <span className="muted" style={{ marginLeft: 'auto' }}>
                    {pipelineSimulated ? 'Rehearsal replay (not PipeGen)' : 'Annotated DeepStream output'}
                </span>
            </div>
            {mjpeg ? (
                <img src={url} alt="Annotated detection stream"
                    style={{ width: '100%', aspectRatio: '16 / 9', objectFit: 'contain', display: 'block', background: '#020810' }} />
            ) : url ? (
                <iframe title="PipeGen annotated stream" src={url} allow="autoplay"
                    style={{ width: '100%', aspectRatio: '16 / 9', border: 0, display: 'block', background: '#020810' }} />
            ) : (
                <div style={{ aspectRatio: '16 / 9', background: '#020810', display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', gap: 10, padding: 20, textAlign: 'center' }}>
                    <div style={{ fontSize: 40 }}>🎥</div>
                    <div style={{ color: '#7a9cc0', fontSize: 13, maxWidth: 460 }}>
                        Inference runs in the PipeGen/DeepStream app (TensorRT), not in the browser.
                        Its on-screen display shows the boxes. To embed it here, re-serve the RTSP sink with MediaMTX and set
                        {' '}<code>VITE_STREAM_URL</code> (see perception/README.md).
                    </div>
                </div>
            )}
        </div>
    );
}

function EventFeed() {
    const { feed } = useLive();
    return (
        <div className="glass-card" style={{ padding: '18px 20px' }}>
            <div className="section-title">⚡ Live loop events <span className="muted">(detection → ESP32 ACK)</span></div>
            {feed.length === 0 ? (
                <div className="empty">Waiting for the first perception event…</div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {feed.slice(0, 8).map((item, idx) => {
                        const d = item.detection || {};
                        const a = item.ack;
                        return (
                            <div key={item.event_id} style={{ padding: '12px 14px', background: '#080e1c', borderRadius: 10,
                                border: `1px solid ${idx === 0 ? 'rgba(0,255,136,0.35)' : '#1e3050'}` }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: idx === 0 ? 10 : 0 }}>
                                    <AnimalTag animal={d.class || a?.profile} />
                                    {a?.severity && <SeverityTag severity={a.severity} />}
                                    {d.confidence != null && <span style={{ color: '#00ff88', fontWeight: 700, fontSize: 13 }}>{(d.confidence * 100).toFixed(0)}%</span>}
                                    {d.track_id != null && d.track_id >= 0 && <span className="muted">track #{d.track_id}</span>}
                                    {d.synthetic && <span style={{ fontSize: 10, color: '#ffd60a', fontWeight: 700 }}>TEST</span>}
                                    <span style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 700,
                                        color: item.timeout ? '#ff3b6b' : a ? (a.state === 'IGNORED' ? '#7a9cc0' : '#00ff88') : '#ffb300' }}>
                                        {item.timeout ? 'NO ACK' : a ? `${a.state}${a.reason ? ` (${a.reason})` : ''} · ${formatMs(a.latency_ms)}` : 'waiting for ESP32…'}
                                    </span>
                                </div>
                                {idx === 0 && <LoopTimeline item={item} />}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

export default function LiveDetection() {
    return (
        <div className="animate-in">
            <div className="page-header">
                <h1>⚡ <span className="gradient-text">Live Loop</span></h1>
                <p>PipeGen sees → bridge confirms → MQTT → ESP32 warns drivers → ACK with measured latency</p>
            </div>
            <LoopStatusStrip />
            <div className="grid-main-side">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 }}>
                    <StreamPanel />
                    <EventFeed />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <SensorPanel />
                    <TelemetryPanel />
                </div>
            </div>
        </div>
    );
}

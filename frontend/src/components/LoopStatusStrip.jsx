import { useEffect, useState } from 'react';
import { useLoopStatus } from '../live/LiveContext';
import { getPipelineInfo } from '../services/api';
import { formatAgo, formatMs } from '../utils/animals';

function Cell({ label, ok, value, sub, warn, sim }) {
    const color = ok ? '#00ff88' : warn ? '#ffb300' : '#ff3b6b';
    return (
        <div className="loop-cell">
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className={`status-dot ${ok ? 'active' : 'inactive'}`} style={{ background: color }} />
                <span className="loop-label">{label}</span>
                {sim && <span className="sim-badge">SIM</span>}
            </div>
            <div className="loop-value" style={{ color }}>{value}</div>
            {sub && <div className="loop-sub">{sub}</div>}
        </div>
    );
}

/** Closed-loop status: Camera -> PipeGen -> Bridge -> Broker -> ESP32 -> ACK. */
export default function LoopStatusStrip() {
    const s = useLoopStatus();
    const [info, setInfo] = useState(null);
    useEffect(() => { getPipelineInfo().then(r => setInfo(r.data)).catch(() => setInfo(null)); }, []);
    const precision = info?.live_engine?.precision;
    const ack = s.lastAck;
    const arrow = <span className="loop-arrow">→</span>;
    return (
        <div className="glass-card loop-strip">
            <Cell label="PipeGen pipeline" ok={s.pipelineAlive} sim={s.pipelineSimulated}
                value={s.pipelineAlive ? `${s.pipelineFps ?? '—'} FPS` : 'NO DATA'}
                sub={s.pipelineSimulated ? 'replay · ONNX on CPU' : precision ? `TensorRT ${precision}` : 'TensorRT engine'} />
            {arrow}
            <Cell label="Bridge" ok={s.bridgeOnline} value={s.bridgeOnline ? 'ONLINE' : 'OFFLINE'}
                sub="filter · K-frames · fuse" />
            {arrow}
            <Cell label="MQTT broker" ok={s.brokerConnected} value={s.brokerConnected ? 'CONNECTED' : 'DOWN'}
                sub={s.apiConnected ? 'dashboard live' : 'dashboard reconnecting…'} />
            {arrow}
            <Cell label={`ESP32 ${s.node.id || ''}`} ok={s.nodeOnline} sim={s.nodeSimulated}
                value={s.nodeOnline ? (s.sensor?.state || 'ONLINE') : 'OFFLINE'}
                sub={s.nodeOnline ? `RSSI ${s.node.rssi ?? '—'} dBm · ${formatAgo(s.node.last_seen_ms, s.now)}` : `last seen ${formatAgo(s.node.last_seen_ms, s.now)}`} />
            {arrow}
            <Cell label="Last alert → ACK" ok={!!ack} warn={!ack}
                value={ack ? formatMs(ack.latency_ms) : '—'}
                sub={ack ? `${ack.profile || ack.state} · on-board ${formatMs(ack.onboard_ms)}` : 'no alert yet'} />
            <div className="loop-divider" />
            <Cell label="Mode" ok={s.mode === 'armed'} warn={!s.mode}
                value={(s.mode || 'unknown').toUpperCase()} sub={s.mode === 'disarmed' ? 'actuation suppressed' : 'actuation enabled'} />
        </div>
    );
}

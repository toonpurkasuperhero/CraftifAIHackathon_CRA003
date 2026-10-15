import { formatMs } from '../utils/animals';

/**
 * Waterfall for one event: capture -> backend sees event on broker -> ESP32 RX -> actuator ON -> ACK.
 * Laptop timestamps (capture, seen, ack) share one clock; ESP32 RX->ACT comes from its own uptime clock.
 */
export default function LoopTimeline({ item }) {
    const d = item?.detection;
    const a = item?.ack;
    if (!d) return null;
    const t0 = d.ts_capture || d.seen_ms;
    const seen = d.seen_ms ? d.seen_ms - t0 : null;
    const total = a?.ack_ts_ms ? a.ack_ts_ms - t0 : null;
    const onboard = a?.onboard_ms ?? null;
    const span = Math.max(total || 0, seen || 0, 1);
    const pct = (v) => `${Math.min(100, Math.max(2, (v / span) * 100))}%`;
    const rows = [
        { label: 'Capture → on broker (PipeGen + bridge)', v: seen, color: '#00b4ff' },
        { label: 'ESP32 RX → actuator ON (on-board)', v: onboard, color: '#ffd60a' },
        { label: 'Capture → ACK back (end to end)', v: total, color: '#00ff88' },
    ];
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rows.map(r => (
                <div key={r.label}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#7a9cc0', marginBottom: 3 }}>
                        <span>{r.label}</span><strong style={{ color: r.color }}>{formatMs(r.v)}</strong>
                    </div>
                    <div style={{ height: 6, background: '#1e3050', borderRadius: 3 }}>
                        {r.v != null && <div style={{ width: pct(r.v), height: '100%', background: r.color, borderRadius: 3 }} />}
                    </div>
                </div>
            ))}
            {item.timeout && <div style={{ color: '#ff3b6b', fontSize: 12, fontWeight: 700 }}>No ACK from the ESP32 (timeout)</div>}
        </div>
    );
}

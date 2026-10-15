import { useEffect, useRef } from 'react';
import { useLive } from '../live/LiveContext';
import { getAnimalInfo, SEVERITY, formatMs } from '../utils/animals';

// Global toasts: one per new physical alert confirmed by the ESP32 ACK.
function Toast({ toast, onClose }) {
    const { ack } = toast;
    const info = getAnimalInfo(ack.profile);
    const sev = SEVERITY[ack.severity] || SEVERITY.WARN;
    const close = useRef(onClose);
    useEffect(() => { close.current = onClose; });
    useEffect(() => {  // one timer per toast, not reset by parent re-renders
        const t = setTimeout(() => close.current(), 6000);
        return () => clearTimeout(t);
    }, [toast.id]);
    return (
        <div className="alert-banner toast" role="alert" style={{ borderColor: sev.color }}>
            <span style={{ fontSize: 26 }}>{info.icon}</span>
            <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 800, color: sev.color, fontSize: 14 }}>
                    {ack.severity} · {info.label} {ack.confirmed ? '· sensor-confirmed' : ''}
                </div>
                <div style={{ fontSize: 12, color: '#e8f4fd', marginTop: 2 }}>
                    Roadside unit actuated · ACK in <strong>{formatMs(ack.latency_ms)}</strong>
                    {ack.onboard_ms != null && <> · on-board {formatMs(ack.onboard_ms)}</>}
                </div>
            </div>
            <button onClick={onClose} aria-label="Dismiss" style={{
                background: 'none', border: 'none', color: '#7a9cc0', cursor: 'pointer', fontSize: 16,
            }}>✕</button>
        </div>
    );
}

export default function AlertToasts() {
    const { toasts, dispatch } = useLive();
    if (!toasts.length) return null;
    return (
        <div className="toast-stack">
            {toasts.map(t => (
                <Toast key={t.id} toast={t} onClose={() => dispatch({ type: 'dismiss', id: t.id })} />
            ))}
        </div>
    );
}

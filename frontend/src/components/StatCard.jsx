export default function StatCard({ icon, label, value, sub, accent, loading }) {
    return (
        <div className="glass-card" style={{
            padding: '22px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            position: 'relative',
            overflow: 'hidden',
        }}>
            {/* BG glow */}
            <div style={{
                position: 'absolute', top: -20, right: -20,
                width: 80, height: 80, borderRadius: '50%',
                background: accent || 'rgba(0,255,136,0.06)',
                filter: 'blur(30px)',
                pointerEvents: 'none',
            }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                    width: 40, height: 40, borderRadius: 10, fontSize: 20,
                    background: accent || 'rgba(0,255,136,0.1)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: '1px solid rgba(0,255,136,0.2)',
                }}>
                    {icon}
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#7a9cc0', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    {label}
                </span>
            </div>

            {loading ? (
                <div style={{ height: 36, background: '#1e3050', borderRadius: 6, animation: 'pulse 1.5s infinite' }} />
            ) : (
                <div style={{ fontSize: 34, fontWeight: 800, color: '#e8f4fd', lineHeight: 1 }}>
                    {value ?? '—'}
                </div>
            )}
            {sub && <div style={{ fontSize: 12, color: '#4a6a8a' }}>{sub}</div>}
        </div>
    );
}

export default function ChartTooltip({ active, payload, label }) {
    if (!active || !payload?.length) return null;
    return (
        <div style={{ background: '#0f1e35', border: '1px solid #1e3050', borderRadius: 8, padding: '8px 14px' }}>
            <p style={{ color: '#7a9cc0', fontSize: 12 }}>{label}</p>
            {payload.map((p, i) => (
                <p key={i} style={{ color: p.color || p.payload?.fill || '#00ff88', fontWeight: 700, fontSize: 14 }}>
                    {p.name}: {p.value}
                </p>
            ))}
        </div>
    );
}

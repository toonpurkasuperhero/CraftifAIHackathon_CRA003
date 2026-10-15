import { getAnimalInfo, SEVERITY, SOURCE_STYLE } from '../utils/animals';

export default function AnimalTag({ animal }) {
    const info = getAnimalInfo(animal);
    return (
        <span className="animal-tag" style={{
            background: info.bg,
            color: info.color,
            border: `1px solid ${info.border}`,
        }}>
            {info.icon} {info.label}
        </span>
    );
}

export function SeverityTag({ severity }) {
    if (!severity) return <span style={{ color: '#4a6a8a', fontSize: 12 }}>—</span>;
    const s = SEVERITY[severity] || SEVERITY.WARN;
    return (
        <span className="animal-tag" style={{ background: s.bg, color: s.color, border: `1px solid ${s.color}` }}>
            {severity}
        </span>
    );
}

export function SourceTag({ source }) {
    const s = SOURCE_STYLE[source] || { label: source, color: '#7a9cc0', bg: 'rgba(122,156,192,0.1)' };
    return (
        <span style={{
            fontSize: 10, padding: '3px 10px', borderRadius: 10, fontWeight: 700, textTransform: 'uppercase',
            background: s.bg, color: s.color, whiteSpace: 'nowrap',
        }}>{s.label}</span>
    );
}

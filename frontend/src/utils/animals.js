// Animal display metadata. Severity/profile values mirror shared/wg_contract.py and the FirmGen PRD.
export const ANIMALS = {
    tapir: {
        label: 'Tapir', color: '#ff8c42', bg: 'rgba(255, 140, 66, 0.15)', border: '#ff8c42', icon: '🦏',
        iucn: 'Vulnerable', baseSeverity: 'CRITICAL', led: 'Fast red strobe 8 Hz + amber', buzzer: '3 long beeps, repeating',
    },
    jaguarundi: {
        label: 'Jaguarundi', color: '#ff3b6b', bg: 'rgba(255, 59, 107, 0.15)', border: '#ff3b6b', icon: '🐱',
        iucn: 'Least Concern', baseSeverity: 'LOW', led: 'Amber blink 1 Hz', buzzer: 'Silent',
    },
    maned_wolf: {
        label: 'Maned Wolf', color: '#ffd60a', bg: 'rgba(255, 214, 10, 0.15)', border: '#ffd60a', icon: '🐺',
        iucn: 'Near Threatened', baseSeverity: 'HIGH', led: 'Red/amber alternate 2 Hz', buzzer: '2 short beeps',
    },
    puma: {
        label: 'Puma', color: '#a78bfa', bg: 'rgba(124, 58, 237, 0.15)', border: '#7c3aed', icon: '🐆',
        iucn: 'Least Concern', baseSeverity: 'MEDIUM', led: 'Slow red pulse 1 Hz', buzzer: '1 beep',
    },
    giant_anteater: {
        label: 'Giant Anteater', color: '#00ff88', bg: 'rgba(0, 255, 136, 0.15)', border: '#00ff88', icon: '🐜',
        iucn: 'Vulnerable', baseSeverity: 'HIGH', led: 'Red strobe 4 Hz', buzzer: '2 beeps',
    },
};

export const SPECIES_KEYS = Object.keys(ANIMALS);

export const SEVERITY = {
    CRITICAL: { color: '#ff3b6b', bg: 'rgba(255,59,107,0.15)', rank: 4 },
    HIGH: { color: '#ff6b35', bg: 'rgba(255,107,53,0.15)', rank: 3 },
    MEDIUM: { color: '#ffd60a', bg: 'rgba(255,214,10,0.15)', rank: 2 },
    LOW: { color: '#00b4ff', bg: 'rgba(0,180,255,0.15)', rank: 1 },
    WARN: { color: '#7a9cc0', bg: 'rgba(122,156,192,0.15)', rank: 0 },
};

export const getAnimalInfo = (key) =>
    ANIMALS[key] || { label: key || 'Unknown', color: '#7a9cc0', bg: 'rgba(122,156,192,0.15)', border: '#7a9cc0', icon: '🐾' };

export const formatAnimalName = (key) => getAnimalInfo(key).label;

export const formatConfidence = (conf) => (conf == null ? '—' : `${(conf * 100).toFixed(1)}%`);

export const formatMs = (ms) => (ms == null ? '—' : ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`);

export const formatAgo = (tsMs, now = Date.now()) => {
    if (!tsMs) return 'never';
    const s = Math.max(0, Math.round((now - tsMs) / 1000));
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    return `${Math.floor(s / 3600)}h ago`;
};

export const formatTimestamp = (ts) => {
    if (!ts) return '—';
    try {
        const d = new Date(ts.replace(' ', 'T'));
        return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'medium' });
    } catch {
        return ts;
    }
};

export const SOURCE_STYLE = {
    pipegen: { label: 'PipeGen', color: '#00ff88', bg: 'rgba(0,255,136,0.1)' },
    synthetic: { label: 'Test', color: '#ffd60a', bg: 'rgba(255,214,10,0.1)' },
    replay: { label: 'Rehearsal', color: '#ffb300', bg: 'rgba(255,179,0,0.12)' },
    webcam: { label: 'Legacy cam', color: '#4a6a8a', bg: 'rgba(74,106,138,0.15)' },
    image: { label: 'Legacy img', color: '#4a6a8a', bg: 'rgba(74,106,138,0.15)' },
};

export const CHART_COLORS = ['#00ff88', '#00b4ff', '#7c3aed', '#ff6b35', '#ffd60a'];

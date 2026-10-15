import axios from 'axios';

// Override with VITE_API_BASE (see frontend/.env.example). Default: same host as the dashboard, port 8001,
// so a judge's laptop/tablet on the demo LAN works without rebuilding.
const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
export const API_BASE = import.meta.env.VITE_API_BASE || `http://${host}:8001/api`;
export const WS_URL = import.meta.env.VITE_WS_URL || API_BASE.replace(/^http/, 'ws') + '/ws';
// Optional annotated PipeGen stream re-served by MediaMTX (WebRTC/HLS page) - see perception/README.md
export const STREAM_URL = import.meta.env.VITE_STREAM_URL || '';

const api = axios.create({ baseURL: API_BASE, timeout: 6000 });

export const getHealth = () => api.get('/health');
export const getState = () => api.get('/state');
export const getHistory = (params) => api.get('/history', { params });
export const deleteRecord = (id) => api.delete(`/history/${id}`);
export const getAnalytics = () => api.get('/analytics');
export const getLatency = (includeSynthetic = true) =>
    api.get('/metrics/latency', { params: { include_synthetic: includeSynthetic } });
export const getPipelineInfo = () => api.get('/pipeline/info');
export const getSpecies = () => api.get('/species');
export const getNodeHistory = () => api.get('/node/history');

export const setMode = (mode) => api.post('/control/mode', { mode });
export const sendCommand = (cmd, durationS) =>
    api.post('/control/cmd', durationS ? { cmd, duration_s: durationS } : { cmd });
export const testAlert = (species, confidence = 0.9, inRoadZone = true) =>
    api.post('/test/alert', { species, confidence, in_road_zone: inRoadZone });

export const exportCSV = (params) => {
    const query = new URLSearchParams(params).toString();
    window.open(`${API_BASE}/export/csv${query ? '?' + query : ''}`, '_blank');
};
export const downloadEvidence = () => window.open(`${API_BASE}/evidence/report`, '_blank');

/**
 * Live event stream with auto-reconnect (exponential backoff, max 8 s).
 * Returns a close() function.
 */
export function connectEvents(onMessage, onConnection) {
    let ws;
    let closed = false;
    let delay = 500;
    let timer;
    const open = () => {
        ws = new WebSocket(WS_URL);
        ws.onopen = () => { delay = 500; onConnection?.(true); };
        ws.onmessage = (e) => {
            try { onMessage(JSON.parse(e.data)); } catch { /* ignore bad frame */ }
        };
        ws.onclose = () => {
            onConnection?.(false);
            if (!closed) timer = setTimeout(open, delay);
            delay = Math.min(delay * 2, 8000);
        };
        ws.onerror = () => ws.close();
    };
    open();
    return () => { closed = true; clearTimeout(timer); ws?.close(); };
}

export default api;

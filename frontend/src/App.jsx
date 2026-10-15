import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import AlertToasts from './components/AlertBanner';
import Dashboard from './pages/Dashboard';
import LiveDetection from './pages/LiveDetection';
import Control from './pages/Control';
import History from './pages/History';
import Analytics from './pages/Analytics';
import { LiveProvider, useLoopStatus } from './live/LiveContext';

function readDemoMode() {
    try { return localStorage.getItem('wg-demo-mode') === '1'; } catch { return false; }
}

function Shell() {
    const s = useLoopStatus();
    const [demo, setDemo] = useState(readDemoMode);

    useEffect(() => {
        document.documentElement.classList.toggle('demo-mode', demo);
        try { localStorage.setItem('wg-demo-mode', demo ? '1' : '0'); } catch { /* storage blocked */ }
    }, [demo]);

    const pill = (ok, label) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div className={`status-dot ${ok ? 'active' : 'inactive'}`} style={{ background: ok ? '#00ff88' : '#ff3b6b' }} />
            <span style={{ fontSize: 11, fontWeight: 600, color: ok ? '#00ff88' : '#ff3b6b' }}>{label}</span>
        </div>
    );

    return (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
            <Sidebar />
            <div className="main-col">
                <header className="topbar">
                    <div style={{ fontSize: 13, color: '#7a9cc0' }}>
                        🌿 WildGuard · Roadside wildlife-collision warning · PipeGen → MQTT → FirmGen ESP32
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                        {pill(s.apiConnected, s.apiConnected ? 'API' : 'API offline')}
                        {pill(s.brokerConnected, 'Broker')}
                        {pill(s.pipelineAlive, 'PipeGen')}
                        {pill(s.nodeOnline, 'ESP32')}
                        <button className="btn-secondary" style={{ padding: '4px 10px', fontSize: 11 }}
                            onClick={() => setDemo(d => !d)} title="Larger text for projectors">
                            {demo ? '🖥 Normal' : '📽 Demo mode'}
                        </button>
                    </div>
                </header>

                {s.rehearsal && (
                    <div className="rehearsal-banner">
                        🎭 REHEARSAL MODE: {[s.pipelineSimulated && 'PipeGen replaced by an ONNX/CPU replay of BRA test images',
                            s.nodeSimulated && 'ESP32 replaced by the contract simulator'].filter(Boolean).join(' · ')}.
                        {' '}Not hardware evidence.
                    </div>
                )}
                {!s.apiConnected && (
                    <div className="offline-banner">
                        ⚠️ Dashboard cannot reach the backend. Start everything with{' '}
                        <code>./scripts/start_all.sh</code> or just the API with{' '}
                        <code>cd backend && python main.py</code>
                    </div>
                )}
                {s.apiConnected && s.node.last_seen_ms && !s.nodeOnline && (
                    <div className="offline-banner">
                        ⚠️ ESP32 node offline (Last Will received or no heartbeat). The roadside unit falls back to
                        sensor-only amber warning until it reconnects.
                    </div>
                )}

                <main className="page-main">
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/live" element={<LiveDetection />} />
                        <Route path="/control" element={<Control />} />
                        <Route path="/history" element={<History />} />
                        <Route path="/analytics" element={<Analytics />} />
                    </Routes>
                </main>

                <footer className="footer">
                    <span>WildGuard AI · YOLOv8n (BRA dataset) on TensorRT via CraftifAI PipeGen · ESP-IDF firmware via CraftifAI FirmGen</span>
                    <span>Tapir · Jaguarundi · Maned Wolf · Puma · Giant Anteater</span>
                </footer>
            </div>
            <AlertToasts />
        </div>
    );
}

export default function App() {
    return (
        <BrowserRouter>
            <LiveProvider>
                <Shell />
            </LiveProvider>
        </BrowserRouter>
    );
}

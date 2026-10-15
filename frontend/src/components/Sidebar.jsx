import { NavLink } from 'react-router-dom';
import {
    MdDashboard, MdVideoCall, MdHistory, MdAnalytics, MdTune
} from 'react-icons/md';
import { useLoopStatus } from '../live/LiveContext';

const navItems = [
    { path: '/', icon: <MdDashboard size={20} />, label: 'Dashboard' },
    { path: '/live', icon: <MdVideoCall size={20} />, label: 'Live Loop' },
    { path: '/control', icon: <MdTune size={20} />, label: 'Control & Test' },
    { path: '/history', icon: <MdHistory size={20} />, label: 'Event History' },
    { path: '/analytics', icon: <MdAnalytics size={20} />, label: 'Analytics' },
];

export default function Sidebar() {
    const s = useLoopStatus();
    const allUp = s.pipelineAlive && s.brokerConnected && s.nodeOnline;
    return (
        <aside className="sidebar" style={{
            width: 240,
            minHeight: '100vh',
            background: 'linear-gradient(180deg, #080e1c 0%, #0a1628 100%)',
            borderRight: '1px solid #1e3050',
            display: 'flex',
            flexDirection: 'column',
            position: 'fixed',
            left: 0, top: 0, bottom: 0,
            zIndex: 100,
        }}>
            {/* Logo */}
            <div style={{ padding: '28px 24px 20px', borderBottom: '1px solid #1e3050' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                        width: 38, height: 38, borderRadius: 10,
                        background: 'linear-gradient(135deg, #00ff88, #00b4ff)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 20,
                    }}>
                        🦁
                    </div>
                    <div>
                        <div style={{ fontWeight: 800, fontSize: 14, color: '#e8f4fd', letterSpacing: 0.3 }}>WildGuard AI</div>
                        <div style={{ fontSize: 10, color: '#4a6a8a', fontWeight: 500, letterSpacing: 1 }}>ROADSIDE CLOSED LOOP</div>
                    </div>
                </div>
            </div>

            {/* Nav */}
            <nav style={{ flex: 1, padding: '16px 12px' }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#4a6a8a', letterSpacing: 1.5, padding: '0 12px 8px' }}>
                    NAVIGATION
                </div>
                {navItems.map(({ path, icon, label }) => (
                    <NavLink
                        key={path}
                        to={path}
                        end={path === '/'}
                        style={({ isActive }) => ({
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            padding: '11px 14px',
                            borderRadius: 10,
                            marginBottom: 4,
                            textDecoration: 'none',
                            fontWeight: 600,
                            fontSize: 14,
                            transition: 'all 0.2s ease',
                            background: isActive
                                ? 'linear-gradient(135deg, rgba(0,255,136,0.12), rgba(0,180,255,0.08))'
                                : 'transparent',
                            color: isActive ? '#00ff88' : '#7a9cc0',
                            borderLeft: isActive ? '3px solid #00ff88' : '3px solid transparent',
                        })}
                    >
                        {icon}
                        {label}
                    </NavLink>
                ))}
            </nav>

            {/* Footer */}
            <div style={{ padding: '16px 24px', borderTop: '1px solid #1e3050' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className={`status-dot ${allUp ? 'active' : 'inactive'}`}
                        style={{ background: allUp ? '#00ff88' : '#ffb300' }} />
                    <span style={{ fontSize: 12, color: allUp ? '#00ff88' : '#ffb300', fontWeight: 600 }}>
                        {allUp ? 'Loop closed' : 'Loop incomplete'}
                    </span>
                </div>
                <div style={{ fontSize: 10, color: '#4a6a8a', marginTop: 4, lineHeight: 1.6 }}>
                    PipeGen {s.pipelineAlive ? '✓' : '✗'} · Broker {s.brokerConnected ? '✓' : '✗'} · ESP32 {s.nodeOnline ? '✓' : '✗'}
                </div>
            </div>
        </aside>
    );
}

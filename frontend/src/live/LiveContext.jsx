/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useReducer, useState } from 'react';
import { connectEvents } from '../services/api';

// Live view of the closed loop, fed by the backend WebSocket (which mirrors MQTT).
const LiveContext = createContext(null);

const MAX_FEED = 50;

const initial = {
    connected: false,     // WebSocket to backend
    snapshot: null,       // full /api/state snapshot
    feed: [],             // [{event_id, detection, ack, timeout}] newest first
    toasts: [],           // alerts to pop up
};

function upsertFeed(feed, eventId, patch) {
    const i = feed.findIndex(f => f.event_id === eventId);
    if (i === -1) return [{ event_id: eventId, ...patch }, ...feed].slice(0, MAX_FEED);
    const next = feed.slice();
    next[i] = { ...next[i], ...patch };
    return next;
}

const touch = (node, ts) => (node ? { ...node, last_seen_ms: ts, reachable: node.status !== 'offline' } : node);

function reducer(state, action) {
    switch (action.type) {
        case 'connection':
            return { ...state, connected: action.value };
        case 'dismiss':
            return { ...state, toasts: state.toasts.filter(t => t.id !== action.id) };
        case 'msg': {
            const { type, data, ts } = action.msg;
            const snap = state.snapshot || {};
            switch (type) {
                case 'snapshot':
                    return { ...state, snapshot: data };
                case 'sensor':  // any node traffic proves the node is alive
                    return { ...state, snapshot: { ...snap, sensor: data, node: touch(snap.node, ts) } };
                case 'telemetry':
                    return { ...state, snapshot: { ...snap, telemetry: data, node: touch(snap.node, ts) } };
                case 'status':
                    return {
                        ...state,
                        snapshot: { ...snap, node: { ...snap.node, ...data, reachable: !!data.online } },
                    };
                case 'mode':
                    return { ...state, snapshot: { ...snap, mode: data } };
                case 'broker':
                    return { ...state, snapshot: { ...snap, broker: data } };
                case 'bridge':
                    return { ...state, snapshot: { ...snap, bridge: data } };
                case 'detection':
                    return {
                        ...state,
                        snapshot: { ...snap, last_detection: data },
                        feed: upsertFeed(state.feed, data.event_id, { detection: data, ts }),
                    };
                case 'ack': {
                    const toasts = data.state === 'ALERT'  // new alerts only, not extensions
                        ? [...state.toasts, { id: `${data.event_id}-${ts}`, ack: data }].slice(-2)
                        : state.toasts;
                    return {
                        ...state,
                        toasts,
                        snapshot: {
                            ...snap,
                            last_ack: data,
                            recent_acks: [data, ...(snap.recent_acks || [])].slice(0, 10),
                            node: snap.node ? { ...snap.node, last_seen_ms: data.ack_ts_ms, reachable: true } : snap.node,
                        },
                        feed: upsertFeed(state.feed, data.event_id, { ack: data }),
                    };
                }
                case 'timeout':
                    return { ...state, feed: upsertFeed(state.feed, data.event_id, { timeout: true }) };
                default:
                    return state;
            }
        }
        default:
            return state;
    }
}

export function LiveProvider({ children }) {
    const [state, dispatch] = useReducer(reducer, initial);

    useEffect(() => connectEvents(
        (msg) => dispatch({ type: 'msg', msg }),
        (value) => dispatch({ type: 'connection', value }),
    ), []);

    return <LiveContext.Provider value={{ ...state, dispatch }}>{children}</LiveContext.Provider>;
}

export function useLive() {
    return useContext(LiveContext);
}

/** Re-render every `ms` so "x s ago" labels and staleness stay current. */
export function useNow(ms = 1000) {
    const [now, setNow] = useState(() => Date.now());
    useEffect(() => {
        const t = setInterval(() => setNow(Date.now()), ms);
        return () => clearInterval(t);
    }, [ms]);
    return now;
}

/** Derived, display-ready loop status. Node/pipeline staleness is re-evaluated client-side. */
export function useLoopStatus() {
    const { snapshot, connected } = useLive();
    const now = useNow(1000);
    const s = snapshot || {};
    const node = s.node || {};
    const sensor = s.sensor || null;
    const nodeFresh = node.last_seen_ms && now - node.last_seen_ms < 5000;
    const bridge = s.bridge || {};
    const pipeFresh = bridge.pipeline_last_ms && now - bridge.pipeline_last_ms < 10000;
    const pipelineSimulated = !!bridge.replay;
    const nodeSimulated = String(node.fw || '').startsWith('sim');
    const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
    return {
        now,
        pipelineSimulated,
        nodeSimulated,
        rehearsal: pipelineSimulated || nodeSimulated,
        streamUrl: bridge.stream_url ? bridge.stream_url.replace('{host}', host) : null,
        apiConnected: connected,
        brokerConnected: !!s.broker?.connected,
        bridgeOnline: bridge.state === 'online',
        pipelineAlive: !!pipeFresh,
        pipelineFps: bridge.fps ?? null,
        nodeOnline: !!(node.online !== false && nodeFresh && node.status !== 'offline'),
        node,
        sensor,
        telemetry: s.telemetry || null,
        mode: s.mode || null,
        lastAck: s.last_ack || null,
        lastDetection: s.last_detection || null,
        recentAcks: s.recent_acks || [],
        counters: s.counters || {},
    };
}

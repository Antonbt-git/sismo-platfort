import { useEffect, useRef, useState } from "react";
import { apiUrl, getToken } from "./api";
import type { SeismicEvent } from "../types";

/**
 * Canal de eventos en tiempo real (Server-Sent Events sobre fetch).
 *
 * La API publica `/api/v1/events/stream` con los eventos observados que llegan
 * a la base de datos; aqui se mantiene UNA sola conexion para toda la app (con
 * reconexion automatica) y se avisa a las paginas para que refresquen sus datos
 * sin que el usuario tenga que sincronizar ni recargar.
 */
export type LiveStatus = "detenido" | "conectando" | "en vivo" | "reconectando";

export interface LiveState {
  status: LiveStatus;
  received: number;
  lastAt: string | null;
}

interface ServerFrame {
  type: "hello" | "events";
  events?: SeismicEvent[];
  server_time?: string;
}

type BatchListener = (events: SeismicEvent[]) => void;
type StateListener = () => void;

const batchListeners = new Set<BatchListener>();
const stateListeners = new Set<StateListener>();

let state: LiveState = { status: "detenido", received: 0, lastAt: null };
let controller: AbortController | null = null;
let connections = 0; // componentes vivos que piden el canal abierto
let epoch = 0; // invalida bucles antiguos al parar o rearrancar
let retryTimer: ReturnType<typeof setTimeout> | null = null;

function publish(patch: Partial<LiveState>) {
  state = { ...state, ...patch };
  stateListeners.forEach((fn) => fn());
}

function notify(events: SeismicEvent[]) {
  batchListeners.forEach((fn) => fn(events));
}

function handleFrame(frame: ServerFrame) {
  if (frame.type === "hello") {
    publish({ status: "en vivo" });
    return;
  }
  if (frame.type === "events" && frame.events && frame.events.length > 0) {
    publish({
      status: "en vivo",
      received: state.received + frame.events.length,
      lastAt: new Date().toISOString(),
    });
    notify(frame.events);
  }
}

async function run(self: number) {
  while (self === epoch && connections > 0) {
    controller = new AbortController();
    try {
      const token = getToken();
      const res = await fetch(apiUrl("/api/v1/events/stream"), {
        headers: {
          Accept: "text/event-stream",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller.signal,
        cache: "no-store",
      });
      if (res.status === 401) {
        publish({ status: "detenido" }); // sesion caducada: api() redirigira al login
        return;
      }
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      publish({ status: "en vivo" });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? ""; // el ultimo fragmento puede estar incompleto
        for (const block of parts) {
          const line = block.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          try {
            handleFrame(JSON.parse(line.slice(5).trim()) as ServerFrame);
          } catch {
            /* trama no valida: se ignora */
          }
        }
      }
      throw new Error("canal cerrado");
    } catch (err) {
      if (self !== epoch || connections === 0) return;
      if ((err as Error).name === "AbortError") return;
      publish({ status: "reconectando" });
      await new Promise<void>((resolve) => {
        retryTimer = setTimeout(resolve, 3000);
      });
    }
  }
}

function start() {
  connections += 1;
  if (connections === 1) {
    epoch += 1;
    publish({ status: "conectando" });
    void run(epoch);
  }
}

function stop() {
  connections = Math.max(0, connections - 1);
  if (connections === 0) {
    epoch += 1;
    controller?.abort();
    controller = null;
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
    publish({ status: "detenido" });
  }
}

/** Estado del canal (estado, recibidos, ultimo evento) para el indicador en vivo. */
export function useLiveState(): LiveState {
  const [, force] = useState(0);
  useEffect(() => {
    const fn = () => force((n) => n + 1);
    stateListeners.add(fn);
    return () => {
      stateListeners.delete(fn);
    };
  }, []);
  return state;
}

/** Mantiene el canal abierto mientras el componente este montado (Layout). */
export function useLiveConnection(): void {
  useEffect(() => {
    start();
    return stop;
  }, []);
}

/** Refresca los datos de la pagina cuando llegan eventos nuevos. */
export function useLiveRefresh(refresh: () => void): void {
  const ref = useRef(refresh);
  ref.current = refresh;
  useEffect(() => {
    const fn: BatchListener = () => ref.current();
    batchListeners.add(fn);
    start();
    return () => {
      batchListeners.delete(fn);
      stop();
    };
  }, []);
}

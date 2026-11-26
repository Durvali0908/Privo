/**
 * src/lib/serverConfig.ts
 *
 * Runtime backend address: validated, persisted in AsyncStorage, cached in memory.
 * No networking here — connection testing lives in api.ts.
 *
 * Resolution order: saved address -> API_BASE_URL (constants.ts).
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import { API_BASE_URL } from "./constants";

export const SERVER_URL_STORAGE_KEY = "privo.serverUrl";
export const DEFAULT_SERVER_URL = API_BASE_URL;

export type NormalizeResult =
    | { ok: true; url: string }
    | { ok: false; reason: string };

const HOST_RE = /^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/;
const IPV4_LIKE_RE = /^\d+(?:\.\d+){3}$/;

const fail = (reason: string): NormalizeResult => ({ ok: false, reason });

/**
 * "192.168.1.7:8000" -> "http://192.168.1.7:8000"
 * Accepts http/https, host or IPv4, optional port. No path, query or credentials.
 */
export function normalizeServerUrl(input: string): NormalizeResult {
    let text = input.trim();
    if (!text) return fail("Enter the server address.");
    if (!text.includes("://")) text = `http://${text}`;

    const m = /^([a-z][a-z0-9+.-]*):\/\/(.*)$/i.exec(text);
    if (!m) return fail("Invalid address.");

    const scheme = m[1].toLowerCase();
    if (scheme !== "http" && scheme !== "https") {
        return fail("Only http:// and https:// addresses are supported.");
    }

    const rest = m[2].replace(/\/+$/, "");
    if (/[\/?#]/.test(rest)) {
        return fail("Enter only the address, without a path (example: http://192.168.1.7:8000).");
    }
    if ((rest.match(/:/g) ?? []).length > 1) {
        return fail("Invalid address (IPv6 is not supported).");
    }

    const [hostRaw, portRaw] = rest.split(":");
    if (!hostRaw) return fail("Enter a host name or IP address.");

    const host = hostRaw.toLowerCase();
    if (!HOST_RE.test(host)) return fail("The host name contains invalid characters.");
    if (IPV4_LIKE_RE.test(host) && host.split(".").some((o) => Number(o) > 255)) {
        return fail("That is not a valid IP address.");
    }

    if (portRaw !== undefined) {
        const port = Number(portRaw);
        if (!/^\d{1,5}$/.test(portRaw) || port < 1 || port > 65535) {
            return fail("The port must be a number between 1 and 65535.");
        }
    }

    return { ok: true, url: `${scheme}://${host}${portRaw !== undefined ? `:${portRaw}` : ""}` };
}

let cached: string | null | undefined; // undefined = not read yet
let loading: Promise<string | null> | null = null;

function readSaved(): Promise<string | null> {
    if (cached !== undefined) return Promise.resolve(cached);
    if (loading === null) {
        loading = AsyncStorage.getItem(SERVER_URL_STORAGE_KEY)
            .then((raw) => {
                const parsed = raw ? normalizeServerUrl(raw) : null;
                cached = parsed && parsed.ok ? parsed.url : null;
                return cached;
            })
            .catch(() => null) // failed reads are not cached; the next call retries
            .finally(() => {
                loading = null;
            });
    }
    return loading;
}

export function getSavedServerUrl(): Promise<string | null> {
    return readSaved();
}

export async function getApiBaseUrl(): Promise<string> {
    return (await readSaved()) ?? DEFAULT_SERVER_URL;
}

export async function saveServerUrl(input: string): Promise<NormalizeResult> {
    const result = normalizeServerUrl(input);
    if (!result.ok) return result;
    try {
        await AsyncStorage.setItem(SERVER_URL_STORAGE_KEY, result.url);
    } catch {
        return fail("Could not save the address on this device. Please try again.");
    }
    cached = result.url;
    return result;
}

export async function clearServerUrl(): Promise<boolean> {
    try {
        await AsyncStorage.removeItem(SERVER_URL_STORAGE_KEY);
    } catch {
        return false;
    }
    cached = null;
    return true;
}
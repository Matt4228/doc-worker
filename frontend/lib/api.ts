const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STORAGE_KEY = "doc-worker:demo-password";
const AUTH_CHANGED = "doc-worker:auth-changed";

export class UnauthorizedError extends Error {
    constructor() {
        super("Demo password required.");
    }
}

// localStorage can throw (private browsing, blocked site data), so every
// access is wrapped. A failed read just means the visitor sees the form.
export function getSavedPassword(): string | null {
    try {
        return localStorage.getItem(STORAGE_KEY);
    } catch {
        return null;
    }
}

function setSavedPassword(password: string | null) {
    try {
        if (password === null) localStorage.removeItem(STORAGE_KEY);
        else localStorage.setItem(STORAGE_KEY, password);
    } catch {
        // Not persisted; the visitor will be asked again next visit.
    }
    window.dispatchEvent(new Event(AUTH_CHANGED));
}

/** For useSyncExternalStore: re-render when the saved password changes,
 *  in this tab (AUTH_CHANGED) or another one ("storage"). */
export function subscribeToAuth(onChange: () => void) {
    window.addEventListener(AUTH_CHANGED, onChange);
    window.addEventListener("storage", onChange);
    return () => {
        window.removeEventListener(AUTH_CHANGED, onChange);
        window.removeEventListener("storage", onChange);
    };
}

export type CheckResult = "ok" | "wrong" | "not-configured" | "unreachable";

/** Verify a password against the backend and save it only if it works. */
export async function unlock(password: string): Promise<CheckResult> {
    let res: Response;
    try {
        res = await fetch(`${API}/auth/check`, {
            headers: { Authorization: `Bearer ${password}` },
        });
    } catch {
        return "unreachable";
    }
    if (res.ok) {
        setSavedPassword(password);
        return "ok";
    }
    if (res.status === 401) return "wrong";
    if (res.status === 503) return "not-configured";
    return "unreachable";
}

/** fetch() against the backend with the saved password attached.
 *
 *  A 401 means the saved password stopped working (e.g. it was changed on
 *  the server), so it's cleared, which sends the visitor back to the
 *  password form, and the caller gets an UnauthorizedError instead of a
 *  401 body it would otherwise try to render. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    const password = getSavedPassword();
    if (password) headers.set("Authorization", `Bearer ${password}`);

    const res = await fetch(`${API}${path}`, { ...init, headers });
    if (res.status === 401) {
        setSavedPassword(null);
        throw new UnauthorizedError();
    }
    return res;
}

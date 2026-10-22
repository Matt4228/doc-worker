"use client";

import { useState, useSyncExternalStore } from "react";
import { CheckResult, getSavedPassword, subscribeToAuth, unlock } from "@/lib/api";

const MESSAGES: Record<Exclude<CheckResult, "ok">, string> = {
    wrong: "Incorrect password.",
    "not-configured": "The server doesn't have a demo password configured yet.",
    unreachable: "Couldn't reach the server. Please try again in a moment.",
};

export default function PasswordGate({ children }: { children: React.ReactNode }) {
    // undefined while rendering on the server and during hydration (there's
    // no localStorage there), null when nothing is saved, otherwise the
    // saved password. Rendering nothing for undefined keeps the server HTML
    // and the first client render identical, so there's no hydration error.
    const saved = useSyncExternalStore(subscribeToAuth, getSavedPassword, () => undefined);

    const [password, setPassword] = useState("");
    const [checking, setChecking] = useState(false);
    const [error, setError] = useState<string | null>(null);

    if (saved === undefined) return null;
    if (saved !== null) return <>{children}</>;

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!password || checking) return;
        setChecking(true);
        setError(null);
        const result = await unlock(password);
        setChecking(false);
        if (result === "ok") setPassword("");
        else setError(MESSAGES[result]);
    };

    return (
        <main className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center px-6">
            <form onSubmit={submit} className="w-full max-w-sm">
                <h1 className="text-3xl font-semibold tracking-tight text-white mb-2">Doc Worker</h1>
                <p className="text-gray-400 text-sm mb-8">This demo is password protected.</p>

                <label htmlFor="demo-password" className="block text-sm text-gray-300 mb-2">
                    Demo password
                </label>
                <input
                    id="demo-password"
                    type="password"
                    autoComplete="current-password"
                    autoFocus
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 focus:outline-none focus:border-blue-500 transition-colors"
                />

                <button
                    type="submit"
                    disabled={checking || !password}
                    className="mt-4 w-full px-5 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-colors"
                >
                    {checking ? "Checking..." : "Continue"}
                </button>

                {/* Free-tier backends sleep when idle, so the first request can be slow. */}
                {checking && (
                    <p className="text-gray-500 text-xs mt-3">
                        The server may be waking up. This can take up to a minute.
                    </p>
                )}
                {error && (
                    <p role="alert" className="text-red-400 text-sm mt-3">
                        {error}
                    </p>
                )}
            </form>
        </main>
    );
}

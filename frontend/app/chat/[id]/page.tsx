"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ChatWindow from "@/components/ChatWindow";
import DocumentPane from "@/components/DocumentPane";
import { apiFetch, UnauthorizedError } from "@/lib/api";
import type { DocumentDetail } from "@/lib/types";

type Load = { status: "loading" } | { status: "ready"; doc: DocumentDetail } | { status: "missing" } | { status: "error" };
type Tab = "document" | "chat";

export default function ChatPage() {
    const { id } = useParams<{ id: string }>();
    const [load, setLoad] = useState<Load>({ status: "loading" });
    // Only used below the lg breakpoint, where the panes become tabs.
    const [tab, setTab] = useState<Tab>("chat");

    useEffect(() => {
        let cancelled = false;
        apiFetch(`/documents/${id}`)
            .then(async (res) => {
                if (res.status === 404 || res.status === 422) return { status: "missing" } as const;
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return { status: "ready", doc: (await res.json()) as DocumentDetail } as const;
            })
            .then((next) => !cancelled && setLoad(next))
            .catch((e) => {
                // A 401 already sent the visitor back to the password form.
                if (!cancelled && !(e instanceof UnauthorizedError)) setLoad({ status: "error" });
            });
        return () => {
            cancelled = true;
        };
    }, [id]);

    const doc = load.status === "ready" ? load.doc : null;

    return (
        <main className="flex h-dvh flex-col bg-gray-950 text-gray-100">
            <header className="flex h-14 shrink-0 items-center gap-3 border-b border-gray-800 px-4">
                <Link
                    href="/"
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-gray-400 hover:bg-gray-900 hover:text-white focus-visible:outline-2 focus-visible:outline-blue-500 transition-colors"
                >
                    <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M15 18l-6-6 6-6" />
                    </svg>
                    Documents
                </Link>
                <h1 className="min-w-0 truncate text-sm font-medium text-white" title={doc?.filename}>
                    {doc?.filename ?? (load.status === "loading" ? "" : "Doc Worker")}
                </h1>

                {doc && (
                    <div role="tablist" aria-label="View" className="ml-auto flex rounded-lg bg-gray-900 p-0.5 lg:hidden">
                        {(["document", "chat"] as const).map((name) => (
                            <button
                                key={name}
                                type="button"
                                role="tab"
                                id={`tab-${name}`}
                                aria-selected={tab === name}
                                aria-controls={`pane-${name}`}
                                onClick={() => setTab(name)}
                                className={`rounded-md px-3 py-1 text-sm capitalize transition-colors focus-visible:outline-2 focus-visible:outline-blue-500 ${
                                    tab === name ? "bg-gray-700 text-white" : "text-gray-400 hover:text-gray-200"
                                }`}
                            >
                                {name}
                            </button>
                        ))}
                    </div>
                )}
            </header>

            {load.status === "missing" && (
                <Notice title="Document not found" body="It may have been deleted. Go back to your documents to pick another one." />
            )}
            {load.status === "error" && (
                <Notice title="Couldn't load this document" body="The server may be waking up. Refresh the page in a moment." />
            )}

            {doc && (
                // Both panes stay mounted on mobile and are only hidden, so
                // switching tabs keeps the PDF's scroll position and any
                // answer that's still loading.
                <div className="flex min-h-0 flex-1">
                    <section
                        id="pane-document"
                        role="tabpanel"
                        aria-labelledby="tab-document"
                        className={`${tab === "document" ? "flex" : "hidden"} min-w-0 flex-1 flex-col bg-gray-900 lg:flex`}
                    >
                        <DocumentPane doc={doc} />
                    </section>
                    <section
                        id="pane-chat"
                        role="tabpanel"
                        aria-labelledby="tab-chat"
                        className={`${tab === "chat" ? "flex" : "hidden"} w-full shrink-0 flex-col lg:flex lg:w-[440px] lg:border-l lg:border-gray-800 xl:w-[480px]`}
                    >
                        <ChatWindow documentId={doc.id} filename={doc.filename} />
                    </section>
                </div>
            )}
        </main>
    );
}

function Notice({ title, body }: { title: string; body: string }) {
    return (
        <div className="flex flex-1 items-center justify-center px-6">
            <div className="max-w-sm text-center">
                <p className="font-medium text-gray-100">{title}</p>
                <p className="mt-2 text-sm text-gray-400">{body}</p>
                <Link href="/" className="mt-4 inline-block text-sm text-blue-400 underline-offset-2 hover:underline">
                    Back to documents
                </Link>
            </div>
        </div>
    );
}

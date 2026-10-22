"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { apiFetch } from "@/lib/api";
import type { DocumentDetail } from "@/lib/types";
import PageSkeleton from "@/components/PageSkeleton";

// pdf.js needs browser APIs, so the viewer is never rendered on the server.
// Loading it lazily also keeps its ~1 MB out of every other page's bundle.
const PdfViewer = dynamic(() => import("@/components/PdfViewer"), {
    ssr: false,
    loading: () => <LoadingPage />,
});

type FileState = { status: "loading" } | { status: "ready"; url: string } | { status: "failed" };

export default function DocumentPane({ doc }: { doc: DocumentDetail }) {
    if (!doc.has_file) {
        return <TextView doc={doc} />;
    }
    return <StoredPdf doc={doc} />;
}

function StoredPdf({ doc }: { doc: DocumentDetail }) {
    const [file, setFile] = useState<FileState>({ status: "loading" });

    // Fetched through apiFetch so the demo password is attached, then handed
    // to pdf.js as a local blob: URL, which needs no headers of its own.
    useEffect(() => {
        let url: string | null = null;
        let cancelled = false;
        apiFetch(`/documents/${doc.id}/file`)
            .then((res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.blob();
            })
            .then((blob) => {
                if (cancelled) return;
                url = URL.createObjectURL(blob);
                setFile({ status: "ready", url });
            })
            .catch(() => {
                if (!cancelled) setFile({ status: "failed" });
            });
        return () => {
            cancelled = true;
            if (url) URL.revokeObjectURL(url);
        };
    }, [doc.id]);

    if (file.status === "loading") return <LoadingPage />;
    if (file.status === "failed") {
        return <TextView doc={doc} notice="The PDF couldn't be displayed, so this is its extracted text." />;
    }
    return <PdfViewer url={file.url} onError={() => setFile({ status: "failed" })} />;
}

function TextView({ doc, notice }: { doc: DocumentDetail; notice?: string }) {
    // PDFs uploaded before originals were stored only have their text.
    const message =
        notice ??
        (doc.content_type === "application/pdf"
            ? "This PDF was uploaded before originals were kept, so only its extracted text is available. Upload it again to see the original layout."
            : undefined);

    return (
        <div className="h-full overflow-y-auto px-6 py-8">
            <article className="mx-auto max-w-[70ch]">
                {message && (
                    <p className="mb-6 rounded-lg border border-gray-800 bg-gray-950/60 px-4 py-3 text-sm text-gray-400">
                        {message}
                    </p>
                )}
                <div className="whitespace-pre-wrap text-[15px] leading-7 text-gray-200">{doc.content}</div>
            </article>
        </div>
    );
}

function LoadingPage() {
    return (
        <div className="flex h-full flex-col">
            <div className="h-11 shrink-0 border-b border-gray-800" />
            <div className="flex flex-1 justify-center overflow-hidden px-6 py-6">
                <PageSkeleton width={480} aspect={11 / 8.5} />
            </div>
        </div>
    );
}

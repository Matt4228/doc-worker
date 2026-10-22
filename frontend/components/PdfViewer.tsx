"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import PageSkeleton from "@/components/PageSkeleton";

// Must be set in the same module that renders <Document>/<Page>, or
// react-pdf's own default can overwrite it (see the react-pdf README).
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url,
).toString();

// Character maps and the standard 14 fonts, which many PDFs reference without
// embedding. Pinned to the bundled pdf.js version so they always match.
const OPTIONS = {
    cMapUrl: `https://unpkg.com/pdfjs-dist@${pdfjs.version}/cmaps/`,
    standardFontDataUrl: `https://unpkg.com/pdfjs-dist@${pdfjs.version}/standard_fonts/`,
};

const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2];
const FIT_INDEX = 2; // 1 = fit to the pane's width

interface Props {
    url: string;
    onError: () => void;
}

export default function PdfViewer({ url, onError }: Props) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const [numPages, setNumPages] = useState(0);
    // Height / width of page 1, used to size pages that haven't rendered yet.
    const [aspect, setAspect] = useState(11 / 8.5);
    const [paneWidth, setPaneWidth] = useState(0);
    const [zoomIndex, setZoomIndex] = useState(FIT_INDEX);
    const [currentPage, setCurrentPage] = useState(1);
    // Pages near the viewport. Only these are drawn, so a 300-page PDF
    // doesn't render 300 canvases up front.
    const [nearby, setNearby] = useState<Set<number>>(() => new Set([1, 2]));

    const zoom = ZOOM_STEPS[zoomIndex];
    // contentRect already excludes the pane's padding, so this is the width
    // available for a page. It's 0 until measured, and while the pane is
    // hidden behind the mobile Chat tab.
    const measured = paneWidth > 0;
    const pageWidth = Math.max(240, Math.floor(paneWidth * zoom));

    useEffect(() => {
        const pane = scrollRef.current;
        if (!pane) return;
        const observer = new ResizeObserver(([entry]) => setPaneWidth(entry.contentRect.width));
        observer.observe(pane);
        return () => observer.disconnect();
    }, []);

    // Start drawing a page when it comes within one screen of the viewport.
    // Waits for the real width: before that, placeholders are sized for the
    // 240px minimum, short enough that every page looks "nearby", and a page
    // marked nearby is never unmarked.
    useEffect(() => {
        const pane = scrollRef.current;
        if (!pane || numPages === 0 || !measured) return;
        const observer = new IntersectionObserver(
            (entries) => {
                const entering = entries
                    .filter((entry) => entry.isIntersecting)
                    .map((entry) => Number((entry.target as HTMLElement).dataset.page));
                if (entering.length === 0) return;
                setNearby((prev) => new Set([...prev, ...entering]));
            },
            { root: pane, rootMargin: "100% 0px" },
        );
        pane.querySelectorAll("[data-page]").forEach((el) => observer.observe(el));
        return () => observer.disconnect();
    }, [numPages, measured]);

    // The page indicator follows whichever page crosses a third of the way
    // down the pane. Measured with getBoundingClientRect rather than offsetTop,
    // which is relative to the nearest positioned ancestor, not this pane.
    const onScroll = useCallback(() => {
        const pane = scrollRef.current;
        if (!pane) return;
        const paneBox = pane.getBoundingClientRect();
        const line = paneBox.top + paneBox.height / 3;
        let page = 1;
        pane.querySelectorAll<HTMLElement>("[data-page]").forEach((el) => {
            if (el.getBoundingClientRect().top <= line) page = Number(el.dataset.page);
        });
        setCurrentPage(page);
    }, []);

    // Keep the current page in view when zooming changes every page's height.
    const changeZoom = (index: number) => {
        const page = currentPage;
        setZoomIndex(index);
        requestAnimationFrame(() => {
            scrollRef.current
                ?.querySelector(`[data-page="${page}"]`)
                ?.scrollIntoView({ block: "start" });
        });
    };

    return (
        <div className="flex h-full min-h-0 flex-col">
            <div className="flex h-11 shrink-0 items-center justify-between border-b border-gray-800 px-4 text-xs text-gray-400">
                <span aria-live="polite" className="tabular-nums">
                    {numPages > 0 ? `Page ${currentPage} of ${numPages}` : "Loading PDF..."}
                </span>
                <div className="flex items-center gap-1">
                    <ToolbarButton
                        label="Zoom out"
                        disabled={zoomIndex === 0}
                        onClick={() => changeZoom(zoomIndex - 1)}
                    >
                        <path d="M5 12h14" />
                    </ToolbarButton>
                    <span className="w-12 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
                    <ToolbarButton
                        label="Zoom in"
                        disabled={zoomIndex === ZOOM_STEPS.length - 1}
                        onClick={() => changeZoom(zoomIndex + 1)}
                    >
                        <path d="M12 5v14M5 12h14" />
                    </ToolbarButton>
                    <button
                        type="button"
                        onClick={() => changeZoom(FIT_INDEX)}
                        disabled={zoomIndex === FIT_INDEX}
                        className="ml-1 rounded-md px-2 py-1 hover:bg-gray-800 hover:text-gray-100 disabled:opacity-40 disabled:hover:bg-transparent focus-visible:outline-2 focus-visible:outline-blue-500 transition-colors"
                    >
                        Fit width
                    </button>
                </div>
            </div>

            <div ref={scrollRef} onScroll={onScroll} className="min-h-0 flex-1 overflow-auto px-6 py-6">
                {/* suspense={false}: react-pdf 11 defaults to Suspense, where a page
                    that starts loading suspends the nearest boundary, which here is
                    the whole viewer. That tore down every drawn page and reset the
                    scroll position each time a new page came into view. It also
                    makes loading, error and onLoadError work (they're ignored
                    under Suspense), so a broken PDF falls back to its text. */}
                <Document
                    suspense={false}
                    file={url}
                    options={OPTIONS}
                    onLoadSuccess={(pdf) => {
                        setNumPages(pdf.numPages);
                        pdf.getPage(1).then((page) => {
                            const viewport = page.getViewport({ scale: 1 });
                            setAspect(viewport.height / viewport.width);
                        });
                    }}
                    onLoadError={onError}
                    loading={<PageSkeleton width={pageWidth} aspect={aspect} />}
                    error={null}
                    className="flex flex-col items-center gap-4"
                >
                    {Array.from({ length: numPages }, (_, i) => i + 1).map((n) => (
                        <div
                            key={n}
                            data-page={n}
                            className="shrink-0 overflow-hidden rounded-sm bg-gray-800/60 shadow-lg shadow-black/40"
                            style={{ width: pageWidth, minHeight: Math.round(pageWidth * aspect) }}
                        >
                            {nearby.has(n) && (
                                <Page pageNumber={n} width={pageWidth} loading={null} />
                            )}
                        </div>
                    ))}
                </Document>
            </div>
        </div>
    );
}

function ToolbarButton({
    label,
    disabled,
    onClick,
    children,
}: {
    label: string;
    disabled: boolean;
    onClick: () => void;
    children: React.ReactNode;
}) {
    return (
        <button
            type="button"
            aria-label={label}
            title={label}
            disabled={disabled}
            onClick={onClick}
            className="grid size-7 place-items-center rounded-md hover:bg-gray-800 hover:text-gray-100 disabled:opacity-40 disabled:hover:bg-transparent focus-visible:outline-2 focus-visible:outline-blue-500 transition-colors"
        >
            <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true">
                {children}
            </svg>
        </button>
    );
}

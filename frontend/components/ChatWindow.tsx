"use client";

import { useState, useRef, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import Markdown from "@/components/Markdown";

interface Message {
    role: "user" | "assistant";
    content: string;
}

interface Props {
    documentId: string;
    filename?: string;
}

// Matches MAX_MESSAGE_CHARS in backend/models.py.
const MAX_MESSAGE_CHARS = 4000;

const GENERIC_ERROR = "Couldn't get an answer. Check your connection and try again.";

/** An error whose message came from the backend and is safe to show as is. */
class ChatError extends Error {}

const SUGGESTIONS = [
    "Summarize this document",
    "What are the key points?",
    "List any dates, deadlines, or numbers it mentions",
];

export default function ChatWindow({ documentId, filename }: Props) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [failed, setFailed] = useState<{ question: string; reason: string } | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        apiFetch(`/chat/${documentId}/history`)
            .then((r) => (r.ok ? r.json() : []))
            .then((data: Message[]) => setMessages(data))
            .catch(console.error);
    }, [documentId]);

    // Scroll the message list itself. scrollIntoView would also scroll any
    // scrollable ancestor, which jumps the whole layout on mobile.
    useEffect(() => {
        const list = scrollRef.current;
        list?.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
    }, [messages, loading]);

    const send = async (text: string) => {
        const question = text.trim();
        if (!question || loading) return;

        const previous = messages;
        setMessages([...previous, { role: "user", content: question }]);
        setInput("");
        setFailed(null);
        setLoading(true);

        try {
            const res = await apiFetch("/chat/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                // Only the new question: the server reads the earlier turns
                // from its own copy of the conversation.
                body: JSON.stringify({ document_id: documentId, message: question }),
            });
            // Without this check an error response's body has no .answer,
            // which used to render as an empty assistant bubble. Busy (503)
            // and AI-service (502) errors explain themselves in `detail`.
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw typeof body?.detail === "string" ? new ChatError(body.detail) : new Error(`HTTP ${res.status}`);
            }
            const data = await res.json();
            setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
        } catch (err) {
            // Take the unanswered question back out so Retry doesn't send it twice.
            setMessages(previous);
            setFailed({ question, reason: err instanceof ChatError ? err.message : GENERIC_ERROR });
        } finally {
            setLoading(false);
        }
    };

    const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        // Enter sends, Shift+Enter adds a line. isComposing skips the Enter
        // that confirms an IME composition (e.g. typing Japanese).
        if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            send(input);
        }
    };

    return (
        <div className="flex h-full min-h-0 flex-col">
            <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-5 py-6">
                {messages.length === 0 && !loading ? (
                    <div className="flex h-full flex-col justify-end gap-4 pb-2">
                        <div>
                            <p className="text-sm font-medium text-gray-200">
                                Ask anything about {filename ?? "this document"}
                            </p>
                            <p className="mt-1 text-sm text-gray-500">
                                Answers come from the document&apos;s text. Try one of these:
                            </p>
                        </div>
                        <div className="flex flex-col items-start gap-2">
                            {SUGGESTIONS.map((suggestion) => (
                                <button
                                    key={suggestion}
                                    type="button"
                                    onClick={() => send(suggestion)}
                                    className="rounded-lg border border-gray-800 px-3 py-2 text-left text-sm text-gray-300 hover:border-gray-600 hover:bg-gray-900 hover:text-gray-100 focus-visible:outline-2 focus-visible:outline-blue-500 transition-colors"
                                >
                                    {suggestion}
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {messages.map((msg, i) =>
                            msg.role === "user" ? (
                                <div key={i} className="flex justify-end">
                                    <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-gray-800 px-4 py-2.5 text-sm leading-relaxed text-gray-100">
                                        {msg.content}
                                    </p>
                                </div>
                            ) : (
                                <Markdown key={i}>{msg.content}</Markdown>
                            ),
                        )}
                        {loading && (
                            <div role="status" className="flex items-center gap-1.5 text-gray-500" aria-label="Thinking">
                                {[0, 150, 300].map((delay) => (
                                    <span
                                        key={delay}
                                        className="size-1.5 animate-pulse rounded-full bg-current motion-reduce:animate-none"
                                        style={{ animationDelay: `${delay}ms` }}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="shrink-0 border-t border-gray-800 p-4">
                {failed && (
                    <div role="alert" className="mb-3 flex items-center justify-between gap-3 text-sm text-red-400">
                        <span>{failed.reason}</span>
                        <button
                            type="button"
                            onClick={() => send(failed.question)}
                            className="shrink-0 rounded-md px-2 py-1 font-medium text-red-300 hover:bg-red-500/10 focus-visible:outline-2 focus-visible:outline-red-400"
                        >
                            Retry
                        </button>
                    </div>
                )}
                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        send(input);
                    }}
                    className="flex items-end gap-2 rounded-xl border border-gray-700 bg-gray-900 p-1.5 focus-within:border-blue-500 transition-colors"
                >
                    <label htmlFor="chat-input" className="sr-only">
                        Ask a question about this document
                    </label>
                    <textarea
                        id="chat-input"
                        rows={1}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={onKeyDown}
                        maxLength={MAX_MESSAGE_CHARS}
                        placeholder="Ask a question about this document..."
                        className="field-sizing-content max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2.5 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none"
                    />
                    <button
                        type="submit"
                        disabled={loading || !input.trim()}
                        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 transition-colors"
                    >
                        Send
                    </button>
                </form>
            </div>
        </div>
    );
}

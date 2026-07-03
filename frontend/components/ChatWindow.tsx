"use client";

import { useState, useRef, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Message {
    role: "user" | "assistant";
    content: string;
}

interface Props {
    documentId: string;
}

export default function ChatWindow({ documentId }: Props) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        fetch(`${API}/chat/${documentId}/history`)
            .then((r) => r.json())
            .then((data) => setMessages(data))
            .catch(console.error);
    }, [documentId]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages])

    const send = async () => {
        const trimmed = input.trim();
        if (!trimmed || loading) return;

        const userMsg: Message = { role: "user", content: trimmed };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            const res = await fetch(`${API}/chat/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    document_id: documentId,
                    message: trimmed,
                    history: messages,
                }),
            });
            const data = await res.json();
            setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
        } catch {
            setMessages((prev) => [
                ...prev,
                { role: "assistant", content: "Something went wrong. Please try again." },
            ]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto space-y-4 pb-6">
                {messages.length === 0 && (
                    <p className="text-gray-500 text-sm text-center mt-12">
                        Ask a question about your document to get started.
                    </p>
                )}
                {messages.map((msg, i) => (
                    <div 
                        key={i}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                        <div
                            className={`max-w-[75%] px-4 py-3 rounded-2x1 text-sm leading-relaxed ${
                                msg.role === "user"
                                    ? "bg-blue-600 text-white rounded-br-sm"
                                    : "bg-gray-800 text-gray-100 rounded-bl-sm"
                            }`}
                        >
                            {msg.content}
                        </div>
                    </div>
                ))}
                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-gray-800 text-gray-400 px-4 py-3 rounded-2x1 rounded-bl-sm text-sm">
                            Thinking...
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            <div className="flex gap-3 pt-4 border-t border-gray-800">
                <input 
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e)  => e.key === "Enter" && !e.shiftKey && send()}
                    placeholder="Ask a question about this document..."
                    className="flex-1 bg-gray-900 border border-gray-700 rounded-x1 px-4 py-3 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 transitions-colors"
                />
                <button 
                    onClick={send}
                    disabled={loading || !input.trim()}
                    className="px-5 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-x1 transition-colors"
                >
                    Send
                </button>
            </div>
        </div>
    );
}
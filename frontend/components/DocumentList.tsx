"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Doc {
    id: string;
    filename: string;
    created_at: string;
}

export default function DocumentList() {
    const [docs, setDocs] = useState<Doc[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${API}/documents/`)
            .then((r) => r.json())
            .then((data) => setDocs(data))
            .catch(console.error)
            .finally(() => setLoading(false));
    }, [])

    if (loading) return <p className="text-gray-500 text-sm">Loading documents...</p>;
    if (docs.length === 0) return <p className="text-gray-500 text-sm">No documents uploaded yet.</p>;

    return (
        <div>
            <h2 className="text-gray-400 text-sm font-medium uppercase tracking widest mb-4">
                Previous Documents
            </h2>
            <ul className="space-y-2">
                {docs.map((doc) => (
                    <li key={doc.id}>
                        <Link 
                            href={`/chat/${doc.id}`}
                            className="flex items-center justify-between px-4 py-3 bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors"
                        >
                            <span className="text-gray-200 text-sm truncate">{doc.filename}</span>
                            <span className="text-gray-500 text-xs ml-4 shrink-0">
                                {new Date(doc.created_at).toLocaleDateString()}
                            </span>
                        </Link>
                    </li>
                ))}
            </ul>
        </div>
    );
}
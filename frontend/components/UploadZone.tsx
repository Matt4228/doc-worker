"use client"

import { useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Props {
    onSuccess: (documentId: string) => void;
}

export default function UploadZone({ onSuccess }: Props) {
    const [dragging, setDragging] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const upload = useCallback(
        async (file: File) => {
            setError(null);
            setUploading(true);
            try {
                const form = new FormData();
                form.append("file", file);
                const res = await fetch(`${API}/documents/upload`, {
                    method: "POST",
                    body: form,
                });
                if (!res.ok) {
                    const data = await res.json();
                    throw new Error(data.detail ?? "Upload failed.");
                }
                const data = await res.json();
                onSuccess(data.id);
            } catch (e: unknown) {
                setError(e instanceof Error ? e.message : "Something went wrong.");
            } finally {
                setUploading(false);
            }
        },
        [onSuccess]
    );

    const onDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setDragging(false);
            const file = e.dataTransfer.files[0];
            if (file) upload(file);
        },
        [upload]
    );

    return (
        <div>
            <label 
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={`flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-xl cursor-pointer transition-colors ${
                    dragging
                        ? "border-blue-500 bg-blue-500/10"
                        : "border-gray-700 hover:border-gray-500 bg-gray-900"
                }`}
            >
                <input 
                    type="file"
                    accept=".pdf,.txt"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
                />
                {uploading ? (
                    <p className="text-gray-400 text-sm">Uploading...</p>
                ) : (
                    <>
                        <p className="text-gray-300 font-medium">Drop a file here or click to upload</p>
                        <p className="text-gray-500 text-sm mt-1">PDF or .txt - up to 10MB</p>
                    </>
                )}
            </label>
            {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
        </div>
    );
}
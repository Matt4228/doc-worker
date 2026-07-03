"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import UploadZone from "@/components/UploadZone";
import DocumentList from "@/components/DocumentList";

export default function Home() {
  const [refresh, setRefresh] = useState(0);
  const router = useRouter();

  const handleUploadSuccess = (documentId: string) => {
    router.push(`/chat/${documentId}`);
  };

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="mb-14">
          <h1 className="text-4xl font-semibold tracking-tight text-white mb-3">
            Doc Worker
          </h1>
          <p className="text-gray-400 text-lg">
            Upload a document. Ask anything about it.
          </p>
        </div>

        <UploadZone
          onSuccess={(id) => {
            setRefresh((r) => r + 1);
            handleUploadSuccess(id);
          }}
        />

        <div className="mt-14">
          <DocumentList key={refresh} />
        </div>
      </div>
    </main>
  );
}
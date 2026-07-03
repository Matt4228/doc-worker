"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import ChatWindow from "@/components/ChatWindow";

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <Link
          href="/"
          className="text-gray-400 hover:text-white text-sm transition-colors"
        >
          ← Back
        </Link>
        <h1 className="text-white font-medium">Doc Worker</h1>
      </header>

      <div className="flex-1 flex flex-col max-w-3xl w-full mx-auto px-6 py-8">
        <ChatWindow documentId={id} />
      </div>
    </main>
  );
}
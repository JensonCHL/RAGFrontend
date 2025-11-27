"use client";

import { useState } from "react";
import { Conversation } from "@/types/chat";

interface ChatHistoryProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export default function ChatHistory({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  isOpen,
  onToggle,
}: ChatHistoryProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const groupedConversations = {
    today: [] as Conversation[],
    yesterday: [] as Conversation[],
    older: [] as Conversation[],
  };

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  conversations
    .filter((conv) =>
      conv.title.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .forEach((conv) => {
      const convDate = new Date(conv.updated_at);
      if (convDate >= today) {
        groupedConversations.today.push(conv);
      } else if (convDate >= yesterday) {
        groupedConversations.yesterday.push(conv);
      } else {
        groupedConversations.older.push(conv);
      }
    });

  const handleRename = (id: string) => {
    if (editTitle.trim()) {
      onRenameConversation(id, editTitle.trim());
      setEditingId(null);
    }
  };

  const renderConversationItem = (conv: Conversation) => (
    <div
      key={conv.id}
      className={`px-4 py-3 cursor-pointer hover:bg-gray-800 transition-colors ${
        conv.id === activeConversationId ? "bg-gray-800" : ""
      }`}
      onClick={() => onSelectConversation(conv.id)}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm truncate flex-1">{conv.title}</p>
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (confirm("Delete this conversation?")) {
              onDeleteConversation(conv.id);
            }
          }}
          className="ml-2 p-1.5 text-gray-500 hover:text-white hover:bg-red-600 rounded transition-colors"
          title="Delete conversation"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
        </button>
      </div>
    </div>
  );

  return (
    <div
      className={`${
        isOpen ? "w-80" : "w-0"
      } bg-gray-900 text-white transition-all duration-300 overflow-hidden flex flex-col relative`}
    >
      {/* Navigation Menu */}
      <div className="p-4 border-b border-gray-700 space-y-1">
        <a
          href="/dashboard"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
            />
          </svg>
          <span className="text-sm font-medium">Dashboard</span>
        </a>
        <a
          href="/file-management"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
            />
          </svg>
          <span className="text-sm font-medium">File Management</span>
        </a>
        <a
          href="/indexing"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
            />
          </svg>
          <span className="text-sm font-medium">Indexing</span>
        </a>
        <a
          href="/chat"
          className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-800 text-white transition-colors"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
          <span className="text-sm font-medium">Chat</span>
        </a>
      </div>

      <div className="p-4 border-b border-gray-700">
        <button
          onClick={onNewConversation}
          className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors duration-200"
        >
          + New Chat
        </button>
      </div>

      <div className="p-4">
        <input
          type="text"
          placeholder="Search conversations..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {groupedConversations.today.length > 0 && (
          <div className="mb-4">
            <h3 className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase">
              Today
            </h3>
            {groupedConversations.today.map(renderConversationItem)}
          </div>
        )}

        {groupedConversations.yesterday.length > 0 && (
          <div className="mb-4">
            <h3 className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase">
              Yesterday
            </h3>
            {groupedConversations.yesterday.map(renderConversationItem)}
          </div>
        )}

        {groupedConversations.older.length > 0 && (
          <div className="mb-4">
            <h3 className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase">
              Older
            </h3>
            {groupedConversations.older.map(renderConversationItem)}
          </div>
        )}
      </div>

      <button
        onClick={onToggle}
        className="absolute top-4 -right-10 bg-gray-900 text-white p-2 rounded-r-lg hover:bg-gray-800"
      >
        <svg
          className={`w-5 h-5 transition-transform ${
            isOpen ? "" : "rotate-180"
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 19l-7-7 7-7"
          />
        </svg>
      </button>
    </div>
  );
}

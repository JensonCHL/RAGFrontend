"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";
import { useSession } from "next-auth/react";
import { Conversation } from "@/types/chat";
import ThemeToggle from "./ThemeToggle";

interface SidebarProps {
  // Chat-specific props (optional)
  conversations?: Conversation[];
  activeConversationId?: string | null;
  onSelectConversation?: (id: string) => void;
  onNewConversation?: () => void;
  onDeleteConversation?: (id: string) => void;
  onRenameConversation?: (id: string, title: string) => void;
  isOpen?: boolean;
  onToggle?: () => void;
}

export default function Sidebar({
  conversations = [],
  activeConversationId = null,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  isOpen = true,
  onToggle,
}: SidebarProps) {
  const { data: session } = useSession();
  const pathname = usePathname();
  const isChatPage = pathname === "/chat";
  const [searchTerm, setSearchTerm] = useState("");

  // Group conversations by date (only for chat page)
  const groupedConversations = {
    today: [] as Conversation[],
    yesterday: [] as Conversation[],
    older: [] as Conversation[],
  };

  if (isChatPage && conversations.length > 0) {
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
  }

  const renderConversationItem = (conv: Conversation) => (
    <div
      key={conv.id}
      className={`group relative mx-2 mb-1 rounded-lg cursor-pointer transition-all ${
        conv.id === activeConversationId
          ? "bg-gray-800 dark:bg-gray-700"
          : "hover:bg-gray-800 dark:hover:bg-gray-700"
      }`}
      onClick={() => onSelectConversation?.(conv.id)}
    >
      <div className="flex items-center gap-3 px-3 py-3">
        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none">
          <rect
            x="4"
            y="4"
            width="6"
            height="6"
            rx="1"
            className="fill-blue-500"
          />
          <rect
            x="14"
            y="4"
            width="6"
            height="6"
            rx="1"
            className="fill-blue-400"
          />
          <rect
            x="4"
            y="14"
            width="6"
            height="6"
            rx="1"
            className="fill-blue-600"
          />
          <rect
            x="14"
            y="14"
            width="6"
            height="6"
            rx="1"
            className="fill-blue-300"
          />
        </svg>
        <p className="text-sm truncate flex-1">{conv.title}</p>
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (confirm("Delete this conversation?")) {
              onDeleteConversation?.(conv.id);
            }
          }}
          className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-white rounded transition-all"
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
      } bg-gray-900 dark:bg-gray-900 text-white transition-all duration-300 overflow-hidden flex flex-col relative border-r border-gray-700 dark:border-gray-700 flex-shrink-0`}
    >
      {/* Logo and Theme Toggle */}
      <div className="p-4 flex items-center justify-between">
        <img
          src="/cloudeka-logo1.png"
          alt="Cloudeka Logo"
          className="h-18 w-auto"
        />
        <ThemeToggle />
      </div>

      {/* Navigation Menu */}
      <div className="p-4 border-b border-gray-700 space-y-1">
        <a
          href="/dashboard"
          className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
            pathname === "/dashboard"
              ? "bg-gray-800 text-white"
              : "text-gray-300 hover:bg-gray-800 hover:text-white"
          }`}
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
          className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
            pathname === "/file-management"
              ? "bg-gray-800 text-white"
              : "text-gray-300 hover:bg-gray-800 hover:text-white"
          }`}
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
          className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
            pathname === "/indexing"
              ? "bg-gray-800 text-white"
              : "text-gray-300 hover:bg-gray-800 hover:text-white"
          }`}
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
          className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
            pathname === "/chat"
              ? "bg-gray-800 text-white"
              : "text-gray-300 hover:bg-gray-800 hover:text-white"
          }`}
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

        {/* Admin Panel Link */}
        {/* @ts-ignore */}
        {(session?.user?.role === "admin" ||
          session?.user?.email?.includes("admin") ||
          session?.user?.name?.includes("Admin")) && (
          <div className="pt-2 mt-2 border-t border-gray-700">
            <a
              href="/admin"
              className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 hover:text-blue-300 border border-blue-600/30"
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
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
              <span className="text-sm font-medium">Admin Panel</span>
            </a>
          </div>
        )}
      </div>

      {/* Chat-specific section - only show on chat page */}
      {isChatPage && (
        <>
          <div className="p-4 border-b border-gray-700">
            <button
              onClick={onNewConversation}
              className="w-full px-4 py-2.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white rounded-lg font-medium transition-all duration-200 shadow-lg shadow-blue-900/20 flex items-center justify-center gap-2"
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
                  d="M12 4v16m8-8H4"
                />
              </svg>
              New Chat
            </button>
          </div>

          <div className="p-4">
            <input
              type="text"
              placeholder="Search conversations..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-4 py-2.5 bg-[#1a1b26] border border-gray-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 placeholder-gray-500 text-gray-300"
            />
          </div>

          <div className="flex-1 overflow-y-auto">
            {groupedConversations.today.length > 0 && (
              <div className="mb-4">
                <h3 className="px-4 py-2 text-xs font-medium text-gray-500">
                  Today
                </h3>
                {groupedConversations.today.map(renderConversationItem)}
              </div>
            )}

            {groupedConversations.yesterday.length > 0 && (
              <div className="mb-4">
                <h3 className="px-4 py-2 text-xs font-medium text-gray-500">
                  Yesterday
                </h3>
                {groupedConversations.yesterday.map(renderConversationItem)}
              </div>
            )}

            {groupedConversations.older.length > 0 && (
              <div className="mb-4">
                <h3 className="px-4 py-2 text-xs font-medium text-gray-500">
                  Previous 7 Days
                </h3>
                {groupedConversations.older.map(renderConversationItem)}
              </div>
            )}
          </div>
        </>
      )}

      {/* Toggle Button */}
      {isChatPage && onToggle && (
        <button
          onClick={onToggle}
          className="absolute top-4 -right-10 bg-gray-900 text-white p-2 rounded-r-lg hover:bg-gray-800 border border-gray-700 border-l-0"
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
      )}
    </div>
  );
}

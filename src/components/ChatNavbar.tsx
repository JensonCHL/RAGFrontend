"use client";

import { useState, useRef, useEffect } from "react";

interface ChatNavbarProps {
  chatTitle?: string;
  onMenuClick?: () => void;
  onRenameChat?: (newTitle: string) => void;
  onDeleteChat?: () => void;
  onPinChat?: () => void;
  isPinned?: boolean;
}

export default function ChatNavbar({
  chatTitle = "New Chat",
  onMenuClick,
  onRenameChat,
  onDeleteChat,
  onPinChat,
  isPinned = false,
}: ChatNavbarProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [newTitle, setNewTitle] = useState(chatTitle);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setNewTitle(chatTitle);
  }, [chatTitle]);

  useEffect(() => {
    if (isRenaming && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isRenaming]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setShowDropdown(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleRename = () => {
    if (newTitle.trim() && newTitle !== chatTitle) {
      onRenameChat?.(newTitle.trim());
    }
    setIsRenaming(false);
    setShowDropdown(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleRename();
    } else if (e.key === "Escape") {
      setNewTitle(chatTitle);
      setIsRenaming(false);
    }
  };

  return (
    <nav className="pt-8 bg-gray-900 flex items-center justify-between px-4 pb-4">
      {/* Left: Brand Name */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 hover:bg-gray-800 rounded-lg transition-colors"
          aria-label="Toggle sidebar"
        >
          <svg
            className="w-5 h-5 text-gray-300"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
        <h1 className="text-xl font-semibold text-white">DekaLLM</h1>
      </div>

      {/* Middle: Chat Title with Dropdown */}
      <div
        className="flex-1 flex justify-center px-4 relative"
        ref={dropdownRef}
      >
        {isRenaming ? (
          <input
            ref={inputRef}
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onBlur={handleRename}
            onKeyDown={handleKeyDown}
            className="text-lg font-medium text-white bg-gray-800 px-3 py-1 rounded-lg max-w-md w-full text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        ) : (
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="flex items-center gap-2 px-3 py-1 hover:bg-gray-800 rounded-lg transition-colors group"
          >
            <h2 className="text-lg font-medium text-gray-300 truncate max-w-md">
              {chatTitle}
            </h2>
            <svg
              className={`w-4 h-4 text-gray-400 transition-transform ${
                showDropdown ? "rotate-180" : ""
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>
        )}

        {/* Dropdown Menu */}
        {showDropdown && !isRenaming && (
          <div className="absolute top-full mt-2 bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 min-w-[200px] z-50">
            <button
              onClick={() => {
                onPinChat?.();
                setShowDropdown(false);
              }}
              className="w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-gray-700 flex items-center gap-3"
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
                  d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
                />
              </svg>
              {isPinned ? "Unpin chat" : "Pin chat"}
            </button>
            <button
              onClick={() => {
                setIsRenaming(true);
                setShowDropdown(false);
              }}
              className="w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-gray-700 flex items-center gap-3"
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
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
              Rename
            </button>
            <button
              onClick={() => {
                if (confirm("Are you sure you want to delete this chat?")) {
                  onDeleteChat?.();
                }
                setShowDropdown(false);
              }}
              className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-gray-700 flex items-center gap-3"
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
              Delete
            </button>
          </div>
        )}
      </div>

      {/* Right: User Profile */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            if (confirm("Are you sure you want to logout?")) {
              window.location.href = "/login";
            }
          }}
          className="flex items-center gap-2 p-2 hover:bg-gray-800 rounded-lg transition-colors group"
        >
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-medium text-lg">
            U
          </div>
          <svg
            className="w-4 h-4 text-gray-400 group-hover:text-white transition-colors hidden sm:block"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>
      </div>
    </nav>
  );
}

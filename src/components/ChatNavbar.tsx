"use client";

import { useState, useRef, useEffect } from "react";
import { useSession, signOut } from "next-auth/react";

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
  const { data: session } = useSession();
  const [showDropdown, setShowDropdown] = useState(false);
  const [showUserDropdown, setShowUserDropdown] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [newTitle, setNewTitle] = useState(chatTitle);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const userDropdownRef = useRef<HTMLDivElement>(null);
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
      if (
        userDropdownRef.current &&
        !userDropdownRef.current.contains(event.target as Node)
      ) {
        setShowUserDropdown(false);
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
    <nav className="pt-4 bg-white dark:bg-gray-900 flex items-center justify-between px-4 pb-4 border-b border-gray-200 dark:border-transparent transition-colors duration-300">
      {/* Left: Brand Name */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          aria-label="Toggle sidebar"
        >
          <svg
            className="w-5 h-5 text-gray-600 dark:text-gray-300"
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
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
          DekaLLM
        </h1>
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
            className="text-lg font-medium text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-800 px-3 py-1 rounded-lg max-w-md w-full text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        ) : (
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="flex items-center gap-2 px-3 py-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors group"
          >
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-300 truncate max-w-md">
              {chatTitle}
            </h2>
            <svg
              className={`w-4 h-4 text-gray-500 dark:text-gray-400 transition-transform ${
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
          <div className="absolute top-full mt-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1 min-w-[200px] z-50">
            <button
              onClick={() => {
                onPinChat?.();
                setShowDropdown(false);
              }}
              className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3"
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
              className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3"
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
              className="w-full px-4 py-2 text-left text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-gray-700 flex items-center gap-3"
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
      <div className="flex items-center gap-3 relative" ref={userDropdownRef}>
        {/* @ts-ignore */}
        {(session?.user?.role === "admin" ||
          session?.user?.email?.includes("admin") ||
          session?.user?.name?.includes("Admin")) && (
          <div className="hidden md:flex items-center gap-1.5 px-3 py-1 bg-blue-100 dark:bg-blue-900/40 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 rounded-full text-xs font-medium shadow-sm">
            <svg
              className="w-3.5 h-3.5"
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
            Admin
          </div>
        )}
        <button
          onClick={() => setShowUserDropdown(!showUserDropdown)}
          className="flex items-center gap-2 p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors group"
        >
          <div className="w-8 h-8 rounded-full overflow-hidden border border-gray-200 dark:border-gray-700">
            <img
              src="/old.png"
              alt="User Profile"
              className="w-full h-full object-cover"
              onError={(e) => {
                // Fallback if image fails
                e.currentTarget.src =
                  "https://ui-avatars.com/api/?name=User&background=0D8ABC&color=fff";
              }}
            />
          </div>
        </button>

        {/* User Dropdown Menu */}
        {showUserDropdown && (
          <div className="absolute top-full right-0 mt-2 w-64 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl py-2 z-50">
            {/* User Info Header */}
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 mb-1">
              <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                {session?.user?.name || "User"}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                {session?.user?.email || "user@example.com"}
              </p>
            </div>

            {/* Menu Items */}
            <div className="py-1">
              {/* Debug Session Role */}
              {/* console.log("Current Session:", session) */}

              {/* @ts-ignore */}
              {(session?.user?.role === "admin" ||
                session?.user?.email?.includes("admin") ||
                session?.user?.name?.includes("Admin")) && (
                <button
                  onClick={() => {
                    // Use window.location for now to ensure full reload if needed, or router
                    window.location.href = "/admin";
                    setShowUserDropdown(false);
                  }}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3"
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
                      d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                  Admin Dashboard
                </button>
              )}

              <button
                onClick={async () => {
                  const currentName = session?.user?.name || "";
                  const newName = prompt("Enter new username:", currentName);

                  if (newName && newName !== currentName) {
                    try {
                      // @ts-ignore
                      const userId = session?.user?.id;
                      if (!userId) {
                        alert("Error: User ID not found");
                        return;
                      }

                      // Check if user is an environment-defined admin (not in database)
                      if (userId?.startsWith("admin-")) {
                        alert(
                          "Environment-defined admin users cannot change their username. Only database-registered users can update their usernames."
                        );
                        return;
                      }

                      const response = await fetch(
                        `/api/proxy/chat/users/me?user_id=${userId}`,
                        {
                          method: "PATCH",
                          headers: {
                            "Content-Type": "application/json",
                          },
                          body: JSON.stringify({ username: newName }),
                        }
                      );

                      if (!response.ok) {
                        const error = await response.json();
                        throw new Error(
                          error.error || "Failed to update username"
                        );
                      }

                      // Force reload to update session
                      window.location.reload();
                    } catch (error) {
                      console.error("Error updating username:", error);
                      alert(
                        error instanceof Error
                          ? error.message
                          : "Failed to update username"
                      );
                    }
                  }
                  setShowUserDropdown(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3"
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
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                  />
                </svg>
                Change Username
              </button>

              <button
                onClick={() => {
                  if (confirm("Are you sure you want to logout?")) {
                    signOut({ callbackUrl: "/login" });
                  }
                  setShowUserDropdown(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-gray-700 flex items-center gap-3"
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
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
                Log out
              </button>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}

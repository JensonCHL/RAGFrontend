"use client";

import { useState, useRef, KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
  isStreaming?: boolean;
  onStop?: () => void;
}

export default function ChatInput({
  onSend,
  disabled,
  isStreaming,
  onStop,
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  return (
    <div className="relative group rounded-3xl p-[1px] overflow-hidden bg-gray-100 dark:bg-gray-900/50 transition-colors duration-300">
      {/* Animated Border Beam - Visible on Focus */}
      <div className="absolute inset-[-100%] animate-[spin_5s_linear_infinite] bg-[conic-gradient(from_90deg_at_50%_50%,#0000_0%,#3b82f6_50%,#ef4444_70%,#0000_100%)] opacity-0 group-focus-within:opacity-100 transition-opacity duration-300" />

      {/* Inner Content */}
      <div className="relative flex items-end gap-2 p-1 rounded-[calc(1.5rem-1px)] bg-white dark:bg-gray-900/90 backdrop-blur-xl h-full w-full">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask DekaLLM"
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-transparent text-gray-900 dark:text-[#AEAEAE] pl-5 py-3 focus:outline-none disabled:cursor-not-allowed max-h-40 overflow-y-auto placeholder-gray-500 dark:placeholder-gray-400"
        />

        {/* Send Button - only shows when there's text */}
        {input.trim() && !isStreaming && (
          <button
            onClick={handleSend}
            disabled={disabled}
            className="mb-2 mr-2 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
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
                d="M5 10l7-7m0 0l7 7m-7-7v18"
              />
            </svg>
          </button>
        )}

        {/* Stop Button - shows when streaming */}
        {isStreaming && (
          <button
            onClick={onStop}
            className="mb-2 mr-2 p-2 bg-red-600 text-white rounded-full hover:bg-red-700 focus:outline-none transition-all duration-200 flex-shrink-0"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <rect x="6" y="6" width="8" height="8" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

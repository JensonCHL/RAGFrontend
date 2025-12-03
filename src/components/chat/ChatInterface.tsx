"use client";

import { useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import { Conversation } from "@/types/chat";

interface ChatInterfaceProps {
  conversation?: Conversation;
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  onStopStreaming?: () => void;
  streamingMessageId?: string | null;
  onEditMessage?: (messageId: string, newContent: string) => void;
  onResendMessage?: (content: string) => void;
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  onStopStreaming,
  streamingMessageId,
  onEditMessage,
  onResendMessage,
}: ChatInterfaceProps) {
  const { data: session } = useSession();
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const userName = session?.user?.name || "User";

  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop =
        messagesContainerRef.current.scrollHeight;
    }
  }, [conversation?.messages]);

  if (!conversation) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-4 pb-32">
        <div className="w-full max-w-4xl space-y-12">
          {/* Greeting */}
          <div className="text-center space-y-2">
            <h1 className="text-5xl font-medium bg-gradient-to-r from-[#3F81F7] to-[#2563eb] bg-clip-text text-transparent">
              Hello, {userName}
            </h1>
            <p className="text-xl text-gray-500 dark:text-gray-400">
              How can I help you today?
            </p>
          </div>

          {/* Floating Island Input */}
          <div className="w-full max-w-3xl mx-auto">
            <div className="bg-white dark:bg-gray-800 rounded-3xl shadow-2xl border border-gray-200 dark:border-gray-700">
              <ChatInput
                onSend={onSendMessage}
                disabled={isLoading}
                isStreaming={isLoading}
                onStop={onStopStreaming}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-white dark:bg-gray-900 transition-colors duration-300">
      {conversation.messages.length === 0 ? (
        // Empty state - Gemini-style greeting with floating input
        <div className="flex-1 flex flex-col items-center justify-center px-4 pb-32">
          <div className="w-full max-w-4xl space-y-12">
            {/* Greeting */}
            <div className="text-center space-y-2">
              <h1 className="text-5xl font-medium animate-cloudeka-gradient">
                Hello, {userName}
              </h1>
              <p className="text-xl text-gray-500 dark:text-gray-400">
                How can I help you today?
              </p>
            </div>

            {/* Floating Island Input */}
            <div className="w-full max-w-3xl mx-auto">
              <div className="bg-white dark:bg-gray-800 rounded-3xl shadow-2xl border border-gray-200 dark:border-gray-700 transition-colors duration-300">
                <ChatInput
                  onSend={onSendMessage}
                  disabled={isLoading}
                  isStreaming={isLoading}
                  onStop={onStopStreaming}
                />
              </div>
            </div>
          </div>
        </div>
      ) : (
        // Messages exist - normal layout with input at bottom
        <>
          <div
            ref={messagesContainerRef}
            className="flex-1 overflow-y-auto px-6 py-8 bg-white dark:bg-gray-900 transition-colors duration-300"
          >
            <div className="max-w-4xl mx-auto">
              {conversation.messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  isStreaming={message.id === streamingMessageId}
                  onEdit={onEditMessage}
                  onResend={onResendMessage}
                />
              ))}
            </div>
          </div>

          <div className="border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-6 py-4 transition-colors duration-300">
            <div className="max-w-4xl mx-auto">
              <div className="bg-white dark:bg-gray-800 rounded-3xl border border-gray-200 dark:border-gray-700 transition-colors duration-300">
                <ChatInput
                  onSend={onSendMessage}
                  disabled={isLoading}
                  isStreaming={isLoading}
                  onStop={onStopStreaming}
                />
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

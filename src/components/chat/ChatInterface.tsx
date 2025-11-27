"use client";

import { useEffect, useRef } from "react";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import { Conversation } from "@/types/chat";

interface ChatInterfaceProps {
  conversation?: Conversation;
  onSendMessage: (content: string) => void;
  isLoading: boolean;
  onStopStreaming?: () => void;
  streamingMessageId?: string | null;
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  onStopStreaming,
  streamingMessageId,
}: ChatInterfaceProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages]);

  if (!conversation) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-gray-100 mb-2">
            Welcome to Chat
          </h2>
          <p className="text-gray-400">Start a new conversation to begin</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      {conversation.messages.length === 0 ? (
        // Empty state - centered input
        <div className="flex-1 flex flex-col items-center justify-center px-4">
          <div className="w-full max-w-3xl space-y-8">
            <div className="text-center">
              <h3 className="text-3xl font-semibold text-gray-100 mb-3">
                How can I help you today?
              </h3>
              <p className="text-gray-400">
                Ask me anything about your documents and I'll search through
                your knowledge base.
              </p>
            </div>

            <div className="w-full">
              <ChatInput
                onSend={onSendMessage}
                disabled={isLoading}
                isStreaming={isLoading}
                onStop={onStopStreaming}
              />
            </div>
          </div>
        </div>
      ) : (
        // Messages exist - normal layout with input at bottom
        <>
          <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
            {conversation.messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                isStreaming={message.id === streamingMessageId}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-gray-700 bg-gray-800 px-4 py-4">
            <ChatInput
              onSend={onSendMessage}
              disabled={isLoading}
              isStreaming={isLoading}
              onStop={onStopStreaming}
            />
          </div>
        </>
      )}
    </div>
  );
}

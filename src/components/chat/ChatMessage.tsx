"use client";

import { Message } from "@/types/chat";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
}

export default function ChatMessage({
  message,
  isStreaming,
}: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} group`}>
      <div className={`max-w-3xl ${isUser ? "ml-12" : "mr-12"}`}>
        <div
          className={`rounded-lg px-4 py-3 ${
            isUser
              ? "bg-blue-600 text-white"
              : "bg-gray-800 border border-gray-700 text-gray-100"
          } shadow-sm`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <>
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    table: ({ node, ...props }) => (
                      <div className="overflow-x-auto my-4">
                        <table
                          className="min-w-full divide-y divide-gray-300 border border-gray-300"
                          {...props}
                        />
                      </div>
                    ),
                    thead: ({ node, ...props }) => (
                      <thead className="bg-gray-50" {...props} />
                    ),
                    tbody: ({ node, ...props }) => (
                      <tbody
                        className="divide-y divide-gray-200 bg-white"
                        {...props}
                      />
                    ),
                    tr: ({ node, ...props }) => <tr {...props} />,
                    th: ({ node, ...props }) => (
                      <th
                        className="px-3 py-2 text-left text-xs font-medium text-gray-900 uppercase tracking-wider border-r border-gray-300 last:border-r-0"
                        {...props}
                      />
                    ),
                    td: ({ node, ...props }) => (
                      <td
                        className="px-3 py-2 text-sm text-gray-700 border-r border-gray-200 last:border-r-0"
                        {...props}
                      />
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
              {isStreaming && (
                <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1" />
              )}
            </>
          )}
        </div>

        <div
          className={`text-xs text-gray-400 mt-1 ${
            isUser ? "text-right" : "text-left"
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString()}
          {isStreaming && (
            <span className="ml-2 text-blue-500">● Streaming...</span>
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2 space-y-2">
            <p className="text-xs font-semibold text-gray-300">Sources:</p>
            {message.sources.map((source, idx) => (
              <div
                key={idx}
                className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm"
              >
                <p className="font-medium text-gray-100">{source.document}</p>
                {source.page && (
                  <p className="text-xs text-gray-400 mt-1">
                    Page {source.page}
                  </p>
                )}
                <p className="text-gray-300 mt-2 line-clamp-2">
                  {source.snippet}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect, useRef } from "react";
import DefaultLayout from "../default-layout";
import ChatInterface from "@/components/chat/ChatInterface";
import Sidebar from "@/components/Sidebar";
import ChatNavbar from "@/components/ChatNavbar";
import { Conversation, Message } from "@/types/chat";
import { v4 as uuidv4 } from "uuid";

function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(
    null
  );
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = () => {
    const stored = localStorage.getItem("chat_conversations");
    if (stored) {
      setConversations(JSON.parse(stored));
    }
  };

  useEffect(() => {
    if (conversations.length > 0) {
      localStorage.setItem("chat_conversations", JSON.stringify(conversations));
    }
  }, [conversations]);

  const createNewConversation = () => {
    const newConversation: Conversation = {
      id: uuidv4(),
      title: "New Conversation",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [],
      user_id: "current-user-id",
    };

    setConversations([newConversation, ...conversations]);
    setActiveConversationId(newConversation.id);
  };

  const sendMessage = async (content: string) => {
    let conversationId = activeConversationId;

    // Create new conversation if none exists
    if (!conversationId) {
      const newConversation: Conversation = {
        id: uuidv4(),
        title: "New Conversation",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [],
        user_id: "current-user-id",
      };

      setConversations([newConversation, ...conversations]);
      setActiveConversationId(newConversation.id);
      conversationId = newConversation.id;
    }

    const userMessage: Message = {
      id: uuidv4(),
      conversation_id: conversationId,
      role: "user",
      content,
      timestamp: new Date().toISOString(),
      status: "sent",
    };

    updateConversationMessages(conversationId, userMessage);

    const botMessageId = uuidv4();
    const botMessage: Message = {
      id: botMessageId,
      conversation_id: conversationId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      status: "sending",
    };

    updateConversationMessages(conversationId, botMessage);
    setStreamingMessageId(botMessageId);
    setIsLoading(true);

    try {
      abortControllerRef.current = new AbortController();

      const response = await fetch("/api/proxy/n8n/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          conversation_id: conversationId,
          user_id: "current-user-id",
          timestamp: new Date().toISOString(),
          messages:
            conversations
              .find((c) => c.id === conversationId)
              ?.messages.map((m) => ({
                role: m.role,
                content: m.content,
              })) || [],
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      await handleSSEStream(response, botMessageId, conversationId);

      const conv = conversations.find((c) => c.id === conversationId);
      if (conv && conv.messages.length === 1) {
        updateConversationTitle(conversationId, content.slice(0, 50) + "...");
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        console.log("Stream aborted by user");
        updateMessageContent(botMessageId, botMessage.content, "error");
      } else {
        console.error("Failed to send message:", error);
        updateMessageContent(
          botMessageId,
          "Error: Failed to get response",
          "error"
        );
      }
    } finally {
      setIsLoading(false);
      setStreamingMessageId(null);
      abortControllerRef.current = null;
    }
  };

  const handleSSEStream = async (
    response: Response,
    messageId: string,
    conversationId: string
  ) => {
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullContent = "";

    if (!reader) throw new Error("No reader available");

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);

            if (data === "[DONE]") {
              updateMessageContent(messageId, fullContent, "sent");
              return;
            }

            try {
              const parsed = JSON.parse(data);

              if (parsed.token) {
                fullContent += parsed.token;
                updateMessageContent(messageId, fullContent, "sending");
              } else if (parsed.content) {
                fullContent += parsed.content;
                updateMessageContent(messageId, fullContent, "sending");
              } else if (parsed.response) {
                fullContent = parsed.response;
                updateMessageContent(
                  messageId,
                  fullContent,
                  "sent",
                  parsed.sources
                );
              }
            } catch (e) {
              fullContent += data;
              updateMessageContent(messageId, fullContent, "sending");
            }
          }
        }
      }

      updateMessageContent(messageId, fullContent, "sent");
    } catch (error) {
      throw error;
    }
  };

  const updateMessageContent = (
    messageId: string,
    content: string,
    status: "sending" | "sent" | "error",
    sources?: any[]
  ) => {
    setConversations((prev) =>
      prev.map((conv) => ({
        ...conv,
        messages: conv.messages.map((msg) =>
          msg.id === messageId
            ? {
                ...msg,
                content,
                status,
                sources,
                timestamp: new Date().toISOString(),
              }
            : msg
        ),
      }))
    );
  };

  const updateConversationMessages = (
    conversationId: string,
    message: Message
  ) => {
    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === conversationId
          ? {
              ...conv,
              messages: [...conv.messages, message],
              updated_at: new Date().toISOString(),
            }
          : conv
      )
    );
  };

  const updateConversationTitle = (conversationId: string, title: string) => {
    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === conversationId ? { ...conv, title } : conv
      )
    );
  };

  const deleteConversation = (conversationId: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== conversationId));
    if (activeConversationId === conversationId) {
      setActiveConversationId(null);
    }
  };

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const activeConversation = conversations.find(
    (c) => c.id === activeConversationId
  );

  return (
    <div
      className="flex overflow-hidden bg-gray-900"
      style={{ height: "100vh" }}
    >
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={setActiveConversationId}
        onNewConversation={createNewConversation}
        onDeleteConversation={deleteConversation}
        onRenameConversation={updateConversationTitle}
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
      />

      <div className="flex-1 flex flex-col">
        <ChatNavbar
          chatTitle={activeConversation?.title || "New Chat"}
          onMenuClick={() => setIsSidebarOpen(!isSidebarOpen)}
          onRenameChat={(newTitle) => {
            if (activeConversationId) {
              updateConversationTitle(activeConversationId, newTitle);
            }
          }}
          onDeleteChat={() => {
            if (activeConversationId) {
              deleteConversation(activeConversationId);
            }
          }}
          onPinChat={() => {
            // Pin functionality can be implemented later
            console.log("Pin chat clicked");
          }}
          isPinned={false}
        />
        <ChatInterface
          conversation={activeConversation}
          onSendMessage={sendMessage}
          isLoading={isLoading}
          onStopStreaming={stopStreaming}
          streamingMessageId={streamingMessageId}
        />
      </div>
    </div>
  );
}

export default function ChatPageWithLayout() {
  return <ChatPage />;
}

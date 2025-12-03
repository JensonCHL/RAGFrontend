"use client";

import { useState, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import DefaultLayout from "../default-layout";
import ChatInterface from "@/components/chat/ChatInterface";
import Sidebar from "@/components/Sidebar";
import ChatNavbar from "@/components/ChatNavbar";
import { Conversation, Message } from "@/types/chat";
import { v4 as uuidv4 } from "uuid";

import { getUserId } from "@/lib/userId";

function ChatPage() {
  const { data: session } = useSession();
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

  // Use session user ID if logged in, otherwise fallback to browser ID
  const userId = session?.user?.email || session?.user?.name || getUserId();

  useEffect(() => {
    loadConversations();
  }, [userId]); // Reload when userId changes (e.g. login/logout)

  useEffect(() => {
    if (activeConversationId) {
      fetchConversationDetails(activeConversationId);
    }
  }, [activeConversationId]);

  const loadConversations = async () => {
    try {
      const response = await fetch(
        `/api/proxy/chat/conversations?user_id=${userId}`
      );
      if (response.ok) {
        const data = await response.json();
        setConversations(data.conversations || []);
      }
    } catch (error) {
      console.error("Failed to load conversations:", error);
      // Fallback to empty array on error
      setConversations([]);
    }
  };

  const fetchConversationDetails = async (conversationId: string) => {
    try {
      const response = await fetch(
        `/api/proxy/chat/conversations/${conversationId}?user_id=${userId}`
      );
      if (response.ok) {
        const data = await response.json();
        // Update the specific conversation with full details (including messages)
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === conversationId
              ? { ...conv, messages: data.messages || [] }
              : conv
          )
        );
      }
    } catch (error) {
      console.error("Failed to load conversation details:", error);
    }
  };

  const createNewConversation = async () => {
    try {
      const response = await fetch("/api/proxy/chat/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          title: "New Conversation",
        }),
      });

      if (response.ok) {
        const newConversation = await response.json();
        setConversations([newConversation, ...conversations]);
        setActiveConversationId(newConversation.id);
      }
    } catch (error) {
      console.error("Failed to create conversation:", error);
    }
  };

  const sendMessage = async (content: string) => {
    let conversationId = activeConversationId;

    // Create new conversation if none exists
    if (!conversationId) {
      try {
        const response = await fetch("/api/proxy/chat/conversations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            title: "New Conversation",
          }),
        });

        if (response.ok) {
          const newConversation = await response.json();
          setConversations([newConversation, ...conversations]);
          setActiveConversationId(newConversation.id);
          conversationId = newConversation.id;
        } else {
          console.error("Failed to create conversation");
          return;
        }
      } catch (error) {
        console.error("Error creating conversation:", error);
        return;
      }
    }

    // Ensure we have a valid conversationId before proceeding
    if (!conversationId) {
      console.error("Failed to get or create conversation");
      return;
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
    saveMessageToBackend(conversationId, userMessage);

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
          user_id: userId,
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

      // Update title if this is the first message
      const conv = conversations.find((c) => c.id === conversationId);
      // Check if it's a new conversation (either empty messages or just the 2 we added)
      const isNewConversation = !conv || conv.messages.length <= 2;

      if (isNewConversation) {
        const newTitle = generateTitle(content);
        updateConversationTitle(conversationId, newTitle);
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

  const saveMessageToBackend = async (
    conversationId: string,
    message: Message
  ) => {
    try {
      await fetch(`/api/proxy/chat/conversations/${conversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          role: message.role,
          content: message.content,
          sources: message.sources,
        }),
      });
    } catch (error) {
      console.error("Failed to save message:", error);
    }
  };

  const generateTitle = (content: string): string => {
    // Get first sentence (split by . ? ! or newline)
    const firstSentence = content.split(/[.?!]|\n/)[0].trim();

    // Truncate if too long (e.g. 40 chars)
    if (firstSentence.length > 40) {
      return firstSentence.substring(0, 40) + "..";
    }

    return firstSentence;
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
              // Save assistant message to backend when done
              saveMessageToBackend(conversationId, {
                id: messageId,
                conversation_id: conversationId,
                role: "assistant",
                content: fullContent,
                timestamp: new Date().toISOString(),
                status: "sent",
              });
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
                // If we get the full response in one go (not typical for stream but possible)
                // We might want to save here, but usually [DONE] follows.
                // Let's rely on [DONE] or the end of stream.
              }
            } catch (e) {
              fullContent += data;
              updateMessageContent(messageId, fullContent, "sending");
            }
          }
        }
      }

      updateMessageContent(messageId, fullContent, "sent");
      // Save assistant message if stream ends without [DONE] (fallback)
      saveMessageToBackend(conversationId, {
        id: messageId,
        conversation_id: conversationId,
        role: "assistant",
        content: fullContent,
        timestamp: new Date().toISOString(),
        status: "sent",
      });
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

  const updateConversationTitle = async (
    conversationId: string,
    title: string
  ) => {
    try {
      const response = await fetch(
        `/api/proxy/chat/conversations/${conversationId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            title,
          }),
        }
      );

      if (response.ok) {
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === conversationId ? { ...conv, title } : conv
          )
        );
      }
    } catch (error) {
      console.error("Failed to update conversation title:", error);
    }
  };

  const deleteConversation = async (conversationId: string) => {
    try {
      const response = await fetch(
        `/api/proxy/chat/conversations/${conversationId}?user_id=${userId}`,
        { method: "DELETE" }
      );

      if (response.ok) {
        setConversations((prev) => prev.filter((c) => c.id !== conversationId));
        if (activeConversationId === conversationId) {
          setActiveConversationId(null);
        }
      }
    } catch (error) {
      console.error("Failed to delete conversation:", error);
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
      className="flex overflow-hidden bg-gray-50 dark:bg-gray-900 transition-colors duration-300"
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

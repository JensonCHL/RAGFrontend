// Chat-related TypeScript types

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  sources?: Source[];
  metadata?: MessageMetadata;
  status?: "sending" | "sent" | "error";
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  user_id: string;
}

export interface Source {
  document: string;
  company?: string;
  page?: number;
  snippet: string;
  score?: number;
}

export interface MessageMetadata {
  tokens_used?: number;
  model?: string;
  processing_time?: number;
}

export interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  isLoading: boolean;
  error: string | null;
}

// n8n Webhook Request/Response Types
export interface N8nChatRequest {
  message: string;
  conversation_id: string;
  user_id: string;
  timestamp: string;
  messages?: Array<{ role: string; content: string }>;
  context?: {
    company?: string;
    document?: string;
  };
}

export interface N8nChatResponse {
  response: string;
  conversation_id: string;
  timestamp: string;
  sources?: Source[];
  metadata?: MessageMetadata;
}

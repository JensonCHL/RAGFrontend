-- Migration: Create chat history tables
-- Description: Creates tables for storing chat conversations and messages with multi-user support
-- Date: 2025-12-02

-- Create conversations table
CREATE TABLE IF NOT EXISTS chat_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for efficient user queries
CREATE INDEX IF NOT EXISTS idx_user_conversations 
ON chat_conversations(user_id, updated_at DESC);

-- Create messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create index for efficient conversation message queries
CREATE INDEX IF NOT EXISTS idx_conversation_messages 
ON chat_messages(conversation_id, created_at ASC);

-- Add comment for documentation
COMMENT ON TABLE chat_conversations IS 'Stores chat conversations with multi-user isolation via user_id';
COMMENT ON TABLE chat_messages IS 'Stores individual messages within conversations';

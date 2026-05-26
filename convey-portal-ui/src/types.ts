// Convey Portal Type Definitions

export interface User {
  email: string;
  session_id: string;
  display_name?: string;
  device_ids?: string[];
}

export interface Session {
  id: string;
  name: string;
  last_message: string;
  time: string;
  unread: number;
  message_count?: number;
  is_active?: boolean;
}

export interface MessageAttachment {
  id: string;
  filename: string;
  url: string;
  type: string;
  size?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  status?: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  reply_to?: string;
  thinking_time?: number;
  attachments?: MessageAttachment[];
  metadata?: Record<string, unknown>;
  isReasoning?: boolean;
  // 工具调用相关字段
  isTool?: boolean;
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  toolElapsed?: number;
}

export interface QuickReply {
  id: string;
  label: string;
  content: string;
}

export interface ChatOptions {
  reasoning_level?: string;
  reply_style?: string;
  model?: string;
}

// SSE Event Types (from Engine)
export interface SSEThinkingEvent {
  type: 'thinking';
  duration: number;
}

export interface SSREReasoningEvent {
  type: 'reasoning';
  content: string;
}

export interface SSEToolEvent {
  type: 'tool';
  name: string;
  status: 'start' | 'end';
  args?: Record<string, unknown>;
  result?: unknown;
}

export interface SSEErrorEvent {
  type: 'error';
  message: string;
}

export interface SSEDoneEvent {
  type: 'done';
  usage?: Record<string, number>;
  options?: ChatOptions;
}

export type SSEEvent =
  | SSEThinkingEvent
  | SSREReasoningEvent
  | SSEToolEvent
  | SSEErrorEvent
  | SSEDoneEvent;

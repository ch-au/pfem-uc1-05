import { create } from 'zustand';
import type { ChatMessage } from '../types/api';

export type ChatStyle = 'Hochdeutsch' | 'Meenzerisch';

interface ChatStore {
  sessionId: string | null;
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  style: ChatStyle;
  setSessionId: (sessionId: string) => void;
  addMessage: (message: ChatMessage) => void;
  setMessages: (messages: ChatMessage[]) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  setStyle: (style: ChatStyle) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  sessionId: null,
  messages: [],
  isLoading: false,
  error: null,
  style: 'Hochdeutsch',
  setSessionId: (sessionId) => set({ sessionId }),
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),
  setMessages: (messages) => set({ messages }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  setStyle: (style) => set({ style }),
  clearMessages: () => set({ messages: [] }),
}));







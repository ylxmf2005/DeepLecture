import { useState, useRef, useEffect } from "react";
import { Send, X, Bot, User, FileText, Image as ImageIcon, Clock, Trash2, Plus, History, FilePlus } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownRenderer } from "@/components/editor/MarkdownRenderer";
import type { AskContextItem, AskMessage } from "@/lib/askTypes";
import {
    askVideoQuestion,
    listAskConversations,
    createAskConversation,
    getAskConversation,
    deleteAskConversation,
    type AskConversationSummary,
} from "@/lib/api";
import { useConfirmDialog } from "@/contexts/ConfirmDialogContext";
import { logger } from "@/shared/infrastructure";
import { toError } from "@/lib/utils/errorUtils";

const log = logger.scope("AskTab");

interface AskTabProps {
    context: AskContextItem[];
    onRemoveContext: (id: string) => void;
    videoId: string;
    learnerProfile?: string;
    subtitleContextWindowSeconds?: number;
    onAddToNotes?: (markdown: string) => void;
    onSeek?: (time: number) => void;
}

export function AskTab({
    context,
    onRemoveContext,
    videoId,
    learnerProfile,
    subtitleContextWindowSeconds,
    onAddToNotes,
    onSeek,
}: AskTabProps) {
    const [messages, setMessages] = useState<AskMessage[]>([]);
    const [conversations, setConversations] = useState<AskConversationSummary[]>([]);
    const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
    const [activeConversationTitle, setActiveConversationTitle] = useState<string>("");
    const [showHistory, setShowHistory] = useState(false);
    const [loadingConversations, setLoadingConversations] = useState(false);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const messagesContainerRef = useRef<HTMLDivElement>(null);
    const { confirm } = useConfirmDialog();

    const scrollToBottom = () => {
        const container = messagesContainerRef.current;
        if (!container) return;
        container.scrollTo({
            top: container.scrollHeight,
            behavior: "smooth",
        });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Load or create the default conversation for this video.
    useEffect(() => {
        let cancelled = false;

        const initConversations = async () => {
            try {
                setLoadingConversations(true);
                const data = await listAskConversations(videoId);
                if (cancelled) return;

                let convs = data.conversations || [];

                if (convs.length === 0) {
                    // Create a default conversation when none exist yet.
                    const created = await createAskConversation(videoId);
                    if (cancelled) return;
                    const summary: AskConversationSummary = {
                        id: created.conversation.id,
                        title: created.conversation.title,
                        createdAt: created.conversation.createdAt,
                        updatedAt: created.conversation.updatedAt,
                        lastMessagePreview:
                            created.conversation.messages[created.conversation.messages.length - 1]?.content ?? "",
                    };
                    convs = [summary];
                }

                setConversations(convs);
                const initial = convs[0];
                setActiveConversationId(initial.id);
                setActiveConversationTitle(initial.title);

                const full = await getAskConversation(videoId, initial.id);
                if (cancelled) return;
                setMessages(full.conversation.messages);
            } catch (error) {
                log.error("Failed to initialize Ask conversations", toError(error), { videoId });
            } finally {
                if (!cancelled) {
                    setLoadingConversations(false);
                }
            }
        };

        if (videoId) {
            initConversations();
        }

        return () => {
            cancelled = true;
        };
    }, [videoId]);

    const handleSelectConversation = async (conversation: AskConversationSummary) => {
        if (conversation.id === activeConversationId) {
            setShowHistory(false);
            return;
        }

        try {
            setLoading(true);
            const full = await getAskConversation(videoId, conversation.id);
            setActiveConversationId(conversation.id);
            setActiveConversationTitle(full.conversation.title);
            setMessages(full.conversation.messages);
        } catch (error) {
            log.error("Failed to load conversation", toError(error), { videoId, conversationId: conversation.id });
        } finally {
            setLoading(false);
            setShowHistory(false);
        }
    };

    const handleCreateConversation = async () => {
        try {
            setLoadingConversations(true);
            const created = await createAskConversation(videoId);
            const summary: AskConversationSummary = {
                id: created.conversation.id,
                title: created.conversation.title,
                createdAt: created.conversation.createdAt,
                updatedAt: created.conversation.updatedAt,
                lastMessagePreview:
                    created.conversation.messages[created.conversation.messages.length - 1]?.content ?? "",
            };
            setConversations((prev) => [summary, ...prev]);
            setActiveConversationId(summary.id);
            setActiveConversationTitle(summary.title);
            setMessages(created.conversation.messages);
            setShowHistory(false);
        } catch (error) {
            log.error("Failed to create conversation", toError(error), { videoId });
        } finally {
            setLoadingConversations(false);
        }
    };

    const handleDeleteConversation = async (conversation: AskConversationSummary) => {
        const confirmed = await confirm({
            title: "Delete Chat",
            message: "Are you sure you want to delete this chat? This action cannot be undone.",
            confirmLabel: "Delete",
            cancelLabel: "Cancel",
            variant: "danger",
        });

        if (!confirmed) return;

        try {
            await deleteAskConversation(videoId, conversation.id);
            setConversations((prev) => prev.filter((c) => c.id !== conversation.id));

            if (conversation.id === activeConversationId) {
                // If the active one was deleted, switch to the next available or clear.
                const remaining = conversations.filter((c) => c.id !== conversation.id);
                if (remaining.length > 0) {
                    await handleSelectConversation(remaining[0]);
                } else {
                    setActiveConversationId(null);
                    setActiveConversationTitle("");
                    setMessages([]);
                }
            }
        } catch (error) {
            log.error("Failed to delete conversation", toError(error), { videoId, conversationId: conversation.id });
        }
    };

    const handleSend = async () => {
        if (loading) return;

        const userMessage = input.trim();
        if (!userMessage) return;

        if (!activeConversationId) {
            // Should not happen in normal flow, but guard just in case.
            return;
        }

        setInput("");

        const newMessages: AskMessage[] = [...messages, { role: "user", content: userMessage }];
        setMessages(newMessages);
        setLoading(true);

        try {
            const response = await askVideoQuestion({
                contentId: videoId,
                conversationId: activeConversationId,
                message: userMessage,
                context,
                learnerProfile,
                subtitleContextWindowSeconds,
            });

            setMessages(prev => [
                ...prev,
                {
                    role: "assistant",
                    content: response.answer,
                },
            ]);
        } catch (error) {
            log.error("Failed to send message", toError(error), { videoId, conversationId: activeConversationId });
            setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I encountered an error while processing your request." }]);
        } finally {
            setLoading(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const activeTitle = activeConversationTitle || "Current chat";

    return (
        <div className="flex flex-col h-full bg-background">
            {/* Header: conversation controls */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-card">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Chat</span>
                    <span className="text-sm font-semibold text-gray-900 dark:text-gray-50 truncate max-w-[160px]" title={activeTitle}>
                        {activeTitle}
                    </span>
                    {loadingConversations && (
                        <span className="text-[10px] text-gray-400">Loading…</span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={handleCreateConversation}
                        className="inline-flex items-center justify-center rounded-full border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-200 p-1.5 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                        title="New chat"
                    >
                        <Plus className="w-4 h-4" />
                    </button>
                    <button
                        type="button"
                        onClick={() => setShowHistory((prev) => !prev)}
                        className={cn(
                            "inline-flex items-center justify-center rounded-full border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-200 p-1.5 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:text-blue-600 dark:hover:text-blue-400 transition-colors",
                            showHistory && "border-blue-500 text-blue-600 dark:text-blue-400"
                        )}
                        title="Chat history"
                    >
                        <History className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* History panel */}
            {showHistory && (
                <div className="border-b border-gray-200 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-900/70 px-3 py-2 max-h-40 overflow-y-auto text-xs space-y-1">
                    {conversations.length === 0 && (
                        <div className="text-gray-400">No chat history yet.</div>
                    )}
                    {conversations.map((conv) => {
                        const isActive = conv.id === activeConversationId;
                        return (
                            <div
                                key={conv.id}
                                className={cn(
                                    "flex items-center justify-between gap-2 px-2 py-1 rounded-md cursor-pointer hover:bg-white/80 dark:hover:bg-gray-800",
                                    isActive && "bg-white dark:bg-gray-800 border border-blue-100 dark:border-blue-800"
                                )}
                                onClick={() => handleSelectConversation(conv)}
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="text-[11px] font-medium text-gray-800 dark:text-gray-100 truncate">
                                        {conv.title}
                                    </div>
                                    {conv.lastMessagePreview && (
                                        <div className="text-[10px] text-gray-400 truncate">
                                            {conv.lastMessagePreview}
                                        </div>
                                    )}
                                </div>
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteConversation(conv);
                                    }}
                                    className="inline-flex items-center justify-center p-1 rounded-full text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
                                    title="Delete chat"
                                >
                                    <Trash2 className="w-3 h-3" />
                                </button>
                            </div>
                        );
                    })}
                </div>
            )}
            {/* Context Area */}
            {context.length > 0 && (
                <div className="p-3 border-b border-border bg-card overflow-x-auto whitespace-nowrap flex gap-2 shrink-0">
                    {context.map((item) => (
                        <div key={item.id} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 text-sm max-w-[200px]">
                            {item.type === 'timeline' && <Clock className="w-3 h-3 text-blue-500" />}
                            {item.type === 'screenshot' && <ImageIcon className="w-3 h-3 text-purple-500" />}
                            {item.type === 'subtitle' && <FileText className="w-3 h-3 text-green-500" />}

                            <span className="truncate text-gray-700 dark:text-gray-300 text-xs">
                                {item.type === 'timeline' && item.title}
                                {item.type === 'screenshot' && `Screenshot ${item.timestamp}s`}
                                {item.type === 'subtitle' && item.text}
                            </span>

                            <button
                                onClick={() => onRemoveContext(item.id)}
                                className="p-0.5 rounded-full hover:bg-blue-100 dark:hover:bg-blue-800 text-gray-400 hover:text-red-500 transition-colors"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                    ))}
                    <button
                        onClick={() => context.forEach(c => onRemoveContext(c.id))}
                        className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    >
                        <Trash2 className="w-3 h-3" />
                        Clear
                    </button>
                </div>
            )}

            {/* Messages Area */}
            <div
                ref={messagesContainerRef}
                className="flex-1 overflow-y-auto p-4 space-y-4"
            >
                {messages.map((msg, idx) => (
                    <div key={idx} className={cn("flex gap-3", msg.role === 'user' ? "justify-end" : "justify-start")}>
                        {msg.role === 'assistant' && (
                            <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                                <Bot className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                            </div>
                        )}

                        <div className={cn(
                            "group relative max-w-[85%]",
                            msg.role === 'user' ? "flex flex-row-reverse gap-2" : "flex flex-row gap-2"
                        )}>
                            <div className={cn(
                                "rounded-2xl px-4 py-3 text-sm shadow-sm",
                                msg.role === 'user'
                                    ? "bg-blue-600 text-white rounded-br-none"
                                    : "bg-card border border-border text-foreground rounded-bl-none"
                            )}>
                                <MarkdownRenderer onSeek={onSeek}>{msg.content}</MarkdownRenderer>
                            </div>

                            {msg.role === 'assistant' && onAddToNotes && (
                                <button
                                    type="button"
                                    onClick={() => {
                                        const heading = `### AI Answer`;
                                        const snippet = `${heading}\n\n${msg.content}`;
                                        onAddToNotes(snippet);
                                    }}
                                    className="opacity-0 group-hover:opacity-100 transition-opacity self-start mt-1 inline-flex items-center justify-center rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 p-1.5 hover:bg-emerald-100 hover:text-emerald-600 dark:hover:bg-emerald-900/30 dark:hover:text-emerald-400"
                                    title="Add to notes"
                                >
                                    <FilePlus className="w-3.5 h-3.5" />
                                </button>
                            )}
                        </div>

                        {msg.role === 'user' && (
                            <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center shrink-0">
                                <User className="w-5 h-5 text-gray-500 dark:text-gray-400" />
                            </div>
                        )}
                    </div>
                ))}
                {loading && (
                    <div className="flex gap-3">
                        <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                            <Bot className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div className="bg-card border border-border rounded-2xl rounded-bl-none px-4 py-3 shadow-sm">
                            <div className="flex gap-1">
                                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-4 bg-card border-t border-border">
                <div className="relative">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask a question about the video..."
                        rows={1}
                        className="w-full pl-4 pr-12 py-3 rounded-xl border border-border bg-background text-foreground text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all resize-none custom-scrollbar max-h-32 placeholder:text-muted-foreground"
                        style={{ minHeight: '46px' }}
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim() || loading}
                        className="absolute right-2 top-1.5 p-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors"
                    >
                        <Send className="w-4 h-4" />
                    </button>
                </div>
                <p className="text-[10px] text-center text-gray-400 mt-2">
                    AI can make mistakes. Please verify important information.
                </p>
            </div>
        </div>
    );
}

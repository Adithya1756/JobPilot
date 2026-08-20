"use client"

import { useState, useRef, useEffect } from "react"
import { useAuth } from "@/hooks/useAuth"
import { agentApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import {
  Send,
  Loader2,
  Bot,
  User,
  Wrench,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  AlertCircle,
} from "lucide-react"

interface Message {
  id: string
  role: "user" | "assistant" | "tool"
  content: string
  toolCalls?: Array<{
    tool: string
    parameters: Record<string, unknown>
    result: Record<string, unknown>
    error: string | null
  }>
  isStreaming?: boolean
}

interface ToolCallDisplay {
  tool: string
  parameters: Record<string, unknown>
  result: Record<string, unknown>
  error: string | null
  expanded: boolean
}

export function ChatInterface({ sessionId }: { sessionId: string }) {
  const { user } = useAuth()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [toolCalls, setToolCalls] = useState<ToolCallDisplay[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input,
    }

    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)
    const currentInput = input
    setInput("")

    try {
      // Convert messages to conversation history format
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }))

      const response = await agentApi.chat(currentInput, history)

      if (response.error) {
        throw new Error(response.error)
      }

      // Add assistant message
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.data?.response || "No response",
        toolCalls: response.data?.tool_calls,
      }

      setMessages((prev) => [...prev, assistantMessage])

      // Store tool calls for display
      if (response.data?.tool_calls) {
        const toolDisplays: ToolCallDisplay[] = response.data.tool_calls.map((tc) => ({
          tool: tc.tool,
          parameters: tc.parameters,
          result: tc.result,
          error: tc.error,
          expanded: false,
        }))
        setToolCalls((prev) => [...prev, ...toolDisplays])
      }
    } catch (error) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend(e)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const formatToolName = (name: string) => {
    return name
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  }

  const getToolIcon = (name: string) => {
    const icons: Record<string, string> = {
      web_search: "🔍",
      research_company: "🏢",
      schedule_interview: "📅",
      check_availability: "📆",
      list_events: "📋",
      generate_follow_up: "📧",
      generate_thank_you: "🙏",
      generate_networking: "🤝",
    }
    return icons[name] || "⚙️"
  }

  return (
    <div className="flex flex-col h-full">
      {/* Tool calls sidebar */}
      {toolCalls.length > 0 && (
        <div className="border-t border-border p-4 bg-muted/30">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold flex items-center gap-2">
              <Wrench className="h-4 w-4" />
              Tools Used ({toolCalls.length})
            </h3>
          </div>
          <ScrollArea className="h-48">
            <div className="space-y-3">
              {toolCalls.map((tc, idx) => (
                <div
                  key={idx}
                  className="border rounded-lg p-3 bg-background"
                >
                  <div
                    className="flex items-center gap-2 cursor-pointer"
                    onClick={() =>
                      setToolCalls((prev) =>
                        prev.map((t, i) => (i === idx ? { ...t, expanded: !t.expanded } : t))
                      )
                    }
                  >
                    <span className="text-lg">{getToolIcon(tc.tool)}</span>
                    <span className="font-mono text-sm font-medium">{formatToolName(tc.tool)}</span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {tc.error ? (
                        <AlertCircle className="h-3 w-3 text-red-500" />
                      ) : (
                        <Check className="h-3 w-3 text-green-500" />
                      )}
                    </span>
                    <ChevronDown className={cn("h-4 w-4 transition-transform", tc.expanded && "rotate-180")} />
                  </div>
                  {tc.expanded && (
                    <div className="mt-2 space-y-2 text-xs">
                      <div>
                        <span className="font-medium text-muted-foreground">Parameters:</span>
                        <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-auto max-h-32">
                          {JSON.stringify(tc.parameters, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <span className="font-medium text-muted-foreground">Result:</span>
                        <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-auto max-h-32">
                          {JSON.stringify(tc.result, null, 2)}
                        </pre>
                      </div>
                      {tc.error && (
                        <div className="text-red-500">
                          <span className="font-medium">Error:</span> {tc.error}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}

      {/* Messages */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                "flex gap-3",
                message.role === "user" && "flex-row-reverse"
              )}
            >
              <div
                className={cn(
                  "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium",
                  message.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : message.role === "tool"
                    ? "bg-muted text-muted-foreground"
                    : "bg-primary text-primary-foreground"
                )}
              >
                {message.role === "user" ? (
                  <User className="h-4 w-4" />
                ) : message.role === "tool" ? (
                  <Wrench className="h-4 w-4" />
                ) : (
                  <Bot className="h-4 w-4" />
                )}
              </div>
              <div
                className={cn(
                  "max-w-[70%] px-4 py-2 rounded-2xl text-sm",
                  message.role === "user"
                    ? "bg-primary text-primary-foreground rounded-tr-none"
                    : message.role === "tool"
                    ? "bg-muted rounded-tl-none"
                    : "bg-muted rounded-tl-none"
                )}
              >
                <div className="whitespace-pre-wrap">{message.content}</div>
                {message.isStreaming && (
                  <Loader2 className="inline-block h-3 w-3 animate-spin ml-2" />
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <form onSubmit={handleSend} className="border-t p-4">
        <div className="flex gap-2">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me to draft a cover letter, research a company, schedule an interview..."
            className="flex-1 min-h-[50px] max-h-[150px] resize-none"
            disabled={isLoading}
            rows={1}
          />
          <Button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="h-10 self-end"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2 text-center">
          Press Enter to send, Shift+Enter for new line
        </p>
      </form>
    </div>
  )
}
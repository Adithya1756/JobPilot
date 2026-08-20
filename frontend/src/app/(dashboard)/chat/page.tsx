"use client"

import { useState, useEffect } from "react"
import { useAuth } from "@/hooks/useAuth"
import { ChatInterface } from "@/components/ChatInterface"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import {
  Plus,
  Trash2,
  MessageSquare,
  Loader2,
  History,
  Sparkles,
  Send,
} from "lucide-react"

interface Session {
  id: string
  created_at: string
  message_count: number
  preview: string
}

export default function ChatPage() {
  const { user } = useAuth()
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [showNewChat, setShowNewChat] = useState(false)

  // Load sessions from localStorage (mock for now - would be API in production)
  useEffect(() => {
    const stored = localStorage.getItem("chat_sessions")
    if (stored) {
      try {
        setSessions(JSON.parse(stored))
      } catch {
        setSessions([])
      }
    }
  }, [])

  const handleNewChat = () => {
    const sessionId = crypto.randomUUID()
    const newSession: Session = {
      id: sessionId,
      created_at: new Date().toISOString(),
      message_count: 0,
      preview: "New conversation",
    }
    const updated = [newSession, ...sessions]
    setSessions(updated)
    localStorage.setItem("chat_sessions", JSON.stringify(updated))
    setCurrentSessionId(sessionId)
    setShowNewChat(false)
  }

  const handleSessionSelect = (sessionId: string) => {
    setCurrentSessionId(sessionId)
  }

  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    const updated = sessions.filter((s) => s.id !== sessionId)
    setSessions(updated)
    localStorage.setItem("chat_sessions", JSON.stringify(updated))
    if (currentSessionId === sessionId) {
      setCurrentSessionId(null)
    }
  }

  // Update session preview when messages change
  // This would be handled by the ChatInterface component in a real implementation

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b bg-background">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <MessageSquare className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">AI Assistant</h1>
            <p className="text-sm text-muted-foreground">
              {currentSessionId ? "Chat with JobPilot" : "Start a new conversation"}
            </p>
          </div>
        </div>
        <Button onClick={() => setShowNewChat(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar - Chat History */}
        <div className="w-80 border-r bg-background flex flex-col hidden md:flex">
          <div className="p-4 border-b">
            <h2 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">
              Conversations
            </h2>
          </div>

          <ScrollArea className="flex-1">
            <div className="p-2 space-y-1">
              {sessions.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  <History className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No conversations yet</p>
                  <p className="text-xs">Click "New Chat" to start</p>
                </div>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    className={cn(
                      "p-3 rounded-lg cursor-pointer transition-colors flex items-start justify-between gap-2",
                      currentSessionId === session.id
                        ? "bg-primary/10"
                        : "hover:bg-muted"
                    )}
                    onClick={() => handleSessionSelect(session.id)}
                  >
                    <div className="flex-1 min-w-0 text-left">
                      <p className="font-medium text-sm truncate">{session.preview}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(session.created_at).toLocaleDateString()}
                        {session.message_count > 0 && (
                          <> · {session.message_count} messages</>
                        )}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => handleDeleteSession(e, session.id)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>

          <div className="p-4 border-t">
            <Button variant="outline" className="w-full" onClick={() => setShowNewChat(true)}>
              <Plus className="h-4 w-4 mr-2" />
              New Chat
            </Button>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {currentSessionId ? (
            <ChatInterface sessionId={currentSessionId} />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
              <div className="p-4 bg-primary/10 rounded-full mb-6">
                <Sparkles className="h-12 w-12 text-primary" />
              </div>
              <h2 className="text-2xl font-semibold mb-2">Welcome to JobPilot</h2>
              <p className="text-muted-foreground max-w-md mb-8">
                Your AI-powered job application assistant. Start a conversation to:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mb-8">
                <Card className="hover:shadow-lg transition-shadow">
                  <CardContent className="p-6">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                        <Send className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">Draft Cover Letters</h3>
                        <p className="text-sm text-muted-foreground">
                          Generate tailored cover letters using your experience
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                <Card className="hover:shadow-lg transition-shadow">
                  <CardContent className="p-6">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                        <Sparkles className="h-5 w-5 text-green-600 dark:text-green-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">Research Companies</h3>
                        <p className="text-sm text-muted-foreground">
                          Get company info for personalized applications
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                <Card className="hover:shadow-lg transition-shadow">
                  <CardContent className="p-6">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                        <History className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">Schedule & Track</h3>
                        <p className="text-sm text-muted-foreground">
                          Manage interviews and follow-ups
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
              <Button size="lg" onClick={handleNewChat}>
                <MessageSquare className="h-4 w-4 mr-2" />
                Start New Conversation
              </Button>
            </div>
          )}

          {/* New Chat Modal */}
          {showNewChat && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
              <Card className="w-full max-w-md mx-4">
                <CardHeader>
                  <CardTitle>Start New Conversation</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground mb-4">
                    This will create a new chat session. Your previous conversations are saved in the sidebar.
                  </p>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowNewChat(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleNewChat}>
                      Create
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
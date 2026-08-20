"use client"

import { useState, useEffect } from "react"
import { useAuth } from "@/hooks/useAuth"
import { agentApi, memoryApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import {
  Save,
  Loader2,
  Copy,
  Check,
  AlertCircle,
  Sparkles,
  FileText,
  ClipboardList,
  ArrowLeft,
} from "lucide-react"

interface ChunkReference {
  chunk_id: string
  content: string
  metadata: Record<string, unknown>
  rerank_score: number
}

interface CritiqueResult {
  strengths: string[]
  weaknesses: string[]
  missing_requirements: string[]
  score: number
  suggestions: string[]
}

interface CoverLetterEditorProps {
  draftId: string
  onBack: () => void
}

export function CoverLetterEditor({ draftId, onBack }: CoverLetterEditorProps) {
  const { user } = useAuth()
  const [content, setContent] = useState("")
  const [originalContent, setOriginalContent] = useState("")
  const [chunks, setChunks] = useState<ChunkReference[]>([])
  const [critique, setCritique] = useState<CritiqueResult | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle")
  const [activeTab, setActiveTab] = useState("editor")

  useEffect(() => {
    loadDraft()
  }, [draftId])

  const loadDraft = async () => {
    try {
      const response = await agentApi.getDraft(draftId)
      if (response.error) throw new Error(response.error)

      const data = response.data
      if (data) {
        setContent(data.content || "")
        setOriginalContent(data.content || "")

        // Load chunk references if available
        if (data.retrieved_chunk_ids && data.retrieved_chunk_ids.length > 0) {
          // We'd need an API endpoint to get chunk details
          // For now, just show placeholder
        }
      }
    } catch (error) {
      console.error("Failed to load draft:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSave = async () => {
    setIsSaving(true)
    setSaveStatus("idle")

    try {
      // Update draft with edited content
      await agentApi.updateDraft(draftId, content)

      // Update style memory from edit
      await memoryApi.updateStyleFromEdit(draftId, originalContent, content)

      setOriginalContent(content)
      setSaveStatus("success")
      setTimeout(() => setSaveStatus("idle"), 3000)
    } catch (error) {
      setSaveStatus("error")
      setTimeout(() => setSaveStatus("idle"), 3000)
    } finally {
      setIsSaving(false)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(content)
  }

  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0
  const charCount = content.length

  if (isLoading) {
    return (
      <div className="flex flex-col h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="mt-4 text-muted-foreground">Loading draft...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b p-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-semibold">Cover Letter Editor</h1>
            <p className="text-sm text-muted-foreground">
              {wordCount} words · {charCount} characters
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleCopy} disabled={!content}>
            <Copy className="h-4 w-4 mr-2" />
            Copy
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || content === originalContent}
            className="bg-primary"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Save Changes
          </Button>
        </div>
      </div>

      {/* Save status toast */}
      {saveStatus === "success" && (
        <div className="fixed bottom-4 right-4 z-50 animate-slide-in">
          <div className="bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
            <Check className="h-4 w-4" />
            Saved successfully
          </div>
        </div>
      )}
      {saveStatus === "error" && (
        <div className="fixed bottom-4 right-4 z-50 animate-slide-in">
          <div className="bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            Failed to save
          </div>
        </div>
      )}

      {/* Main content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <TabsList className="border-b p-1">
          <TabsTrigger value="editor" className="flex-1">
            <FileText className="h-4 w-4 mr-2" />
            Editor
          </TabsTrigger>
          <TabsTrigger value="references" className="flex-1">
            <Sparkles className="h-4 w-4 mr-2" />
            References
          </TabsTrigger>
          <TabsTrigger value="critique" className="flex-1">
            <ClipboardList className="h-4 w-4 mr-2" />
            Critique
          </TabsTrigger>
        </TabsList>

        <TabsContent value="editor" className="flex-1">
          <ScrollArea className="flex-1 p-4">
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Your cover letter will appear here..."
              className="font-mono text-sm h-full min-h-[500px] resize-none"
              spellCheck={true}
            />
          </ScrollArea>
        </TabsContent>

        <TabsContent value="references" className="flex-1">
          <ScrollArea className="flex-1 p-4">
            <div className="space-y-4">
              {chunks.length > 0 ? (
                chunks.map((chunk, idx) => (
                  <Card key={idx}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <span className="text-muted-foreground">Reference #{idx + 1}</span>
                        <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
                          Score: {(chunk.rerank_score * 100).toFixed(0)}%
                        </span>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-sm text-muted-foreground mb-2">
                        Section: {chunk.metadata?.section as string || "Experience"}
                      </div>
                      <pre className="whitespace-pre-wrap text-sm bg-muted p-3 rounded">
                        {chunk.content}
                      </pre>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No reference chunks available for this draft.</p>
                  <p className="text-sm mt-2">Generated drafts include retrieved experience as context.</p>
                </div>
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="critique" className="flex-1">
          <ScrollArea className="flex-1 p-4">
            {critique ? (
              <div className="space-y-6">
                <div>
                  <h3 className="font-semibold mb-3 flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    Self-Critique Score: {critique.score}/100
                  </h3>
                  <div className="bg-primary/10 p-4 rounded-lg">
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary transition-all duration-500"
                        style={{ width: `${critique.score}%` }}
                      />
                    </div>
                  </div>
                </div>

                {critique.strengths.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-2 text-green-600 dark:text-green-400 flex items-center gap-2">
                      <Check className="h-4 w-4" />
                      Strengths
                    </h4>
                    <ul className="space-y-1 pl-4 list-disc text-sm">
                      {critique.strengths.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {critique.weaknesses.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-2 text-red-600 dark:text-red-400 flex items-center gap-2">
                      <AlertCircle className="h-4 w-4" />
                      Areas for Improvement
                    </h4>
                    <ul className="space-y-1 pl-4 list-disc text-sm">
                      {critique.weaknesses.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {critique.missing_requirements.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-2 text-orange-600 dark:text-orange-400">
                      Missing Requirements
                    </h4>
                    <ul className="space-y-1 pl-4 list-disc text-sm">
                      {critique.missing_requirements.map((m, i) => (
                        <li key={i}>{m}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {critique.suggestions.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-2">Suggestions</h4>
                    <ul className="space-y-1 pl-4 list-disc text-sm">
                      {critique.suggestions.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <ClipboardList className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No critique available for this draft.</p>
                <p className="text-sm mt-2">Generate with "Include Critique" option to see feedback.</p>
              </div>
            )}
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  )
}
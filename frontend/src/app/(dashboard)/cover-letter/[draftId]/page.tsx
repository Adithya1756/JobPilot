"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import { CoverLetterEditor } from "@/components/CoverLetterEditor"
import { useAuth } from "@/hooks/useAuth"

export default function CoverLetterPage() {
  const params = useParams()
  const draftId = params.draftId as string
  const { user } = useAuth()
  const [ready, setReady] = useState(true)

  return (
    <div className="h-[calc(100vh-4rem)]">
      <CoverLetterEditor draftId={draftId} onBack={() => window.history.back()} />
    </div>
  )
}

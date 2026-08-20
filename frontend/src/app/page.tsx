import { Button } from "@/components/ui/button"
import Link from "next/link"
import { FileText, Bot, Briefcase } from "lucide-react"

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted">
      {/* Hero */}
      <div className="container mx-auto px-4 py-24 text-center">
        <h1 className="text-5xl font-bold tracking-tight mb-6">
          Your AI-Powered Job Application Assistant
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
          Upload your resume, paste job descriptions, and let AI generate tailored cover letters
          and application answers. Track every application in one place.
        </p>
        <div className="flex gap-4 justify-center">
          <Button asChild size="lg">
            <Link href="/signup">Get Started</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/login">Sign In</Link>
          </Button>
        </div>
      </div>

      {/* Features */}
      <div className="container mx-auto px-4 py-16">
        <div className="grid md:grid-cols-3 gap-8">
          <div className="p-6 rounded-lg border bg-card">
            <FileText className="h-10 w-10 mb-4 text-primary" />
            <h2 className="text-xl font-semibold mb-2">Document Ingestion</h2>
            <p className="text-muted-foreground">
              Upload your resume, project writeups, and past cover letters. We automatically
              parse and chunk them for intelligent retrieval.
            </p>
          </div>

          <div className="p-6 rounded-lg border bg-card">
            <Bot className="h-10 w-10 mb-4 text-primary" />
            <h2 className="text-xl font-semibold mb-2">AI-Powered Drafting</h2>
            <p className="text-muted-foreground">
              Paste a job description and get tailored cover letters and answers. The AI
              retrieves relevant experience from your documents.
            </p>
          </div>

          <div className="p-6 rounded-lg border bg-card">
            <Briefcase className="h-10 w-10 mb-4 text-primary" />
            <h2 className="text-xl font-semibold mb-2">Application Tracker</h2>
            <p className="text-muted-foreground">
              Track every application from saved to offer. Get reminders for follow-ups and
              never lose track of where you applied.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

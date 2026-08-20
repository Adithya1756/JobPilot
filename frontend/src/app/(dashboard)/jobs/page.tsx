"use client"

import { useState, useEffect } from "react"
import { useAuth } from "@/hooks/useAuth"
import { jobsApi, applicationsApi, agentApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Plus, Briefcase, Loader2, Trash2, FileText, Sparkles, CheckCircle } from "lucide-react"

interface Job {
  id: string
  company_name: string
  role_title: string
  job_description: string
  source_url: string | null
  created_at: string
  has_application: boolean
  application_status: string | null
}

const STATUS_COLORS: Record<string, string> = {
  saved: "bg-gray-100 text-gray-800",
  applied: "bg-blue-100 text-blue-800",
  interview: "bg-yellow-100 text-yellow-800",
  offer: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
}

export default function JobsPage() {
  const { user, loading: authLoading } = useAuth()
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [generating, setGenerating] = useState<string | null>(null)
  const [generatedDraft, setGeneratedDraft] = useState<{ content: string; draftId: string } | null>(null)

  // Form state
  const [companyName, setCompanyName] = useState("")
  const [roleTitle, setRoleTitle] = useState("")
  const [jobDescription, setJobDescription] = useState("")
  const [sourceUrl, setSourceUrl] = useState("")
  const [error, setError] = useState("")

  useEffect(() => {
    if (user) {
      fetchJobs()
    }
  }, [user])

  const fetchJobs = async () => {
    setLoading(true)
    const result = await jobsApi.list()
    if (result.data) {
      setJobs(result.data.jobs)
    }
    setLoading(false)
  }

  const handleAddJob = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    const result = await jobsApi.create({
      company_name: companyName,
      role_title: roleTitle,
      job_description: jobDescription,
      source_url: sourceUrl || undefined,
    })

    if (result.error) {
      setError(result.error)
    } else {
      setCompanyName("")
      setRoleTitle("")
      setJobDescription("")
      setSourceUrl("")
      setShowAddForm(false)
      fetchJobs()
    }
  }

  const handleDeleteJob = async (jobId: string) => {
    if (!confirm("Are you sure you want to delete this job?")) return
    await jobsApi.delete(jobId)
    setJobs(jobs.filter((j) => j.id !== jobId))
  }

  const handleGenerateCoverLetter = async (job: Job) => {
    setGenerating(job.id)
    setGeneratedDraft(null)
    setError("")

    const result = await agentApi.generateDraft(job.id, true)

    setGenerating(null)

    if (result.error) {
      setError(result.error)
    } else if (result.data) {
      setGeneratedDraft({
        content: result.data.content,
        draftId: result.data.draft_id,
      })
    }
  }

  const handleMarkApplied = async (job: Job) => {
    const result = await applicationsApi.create({
      job_id: job.id,
      status: "applied",
    })

    if (result.data) {
      fetchJobs()
    }
  }

  if (authLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto py-8 px-4">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold">Jobs</h1>
            <p className="text-muted-foreground">
              Track job applications and generate tailored materials
            </p>
          </div>
          <Button onClick={() => setShowAddForm(!showAddForm)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Job
          </Button>
        </div>

        {/* Add Job Form */}
        {showAddForm && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Add New Job</CardTitle>
              <CardDescription>
                Paste the job description to generate tailored application materials
              </CardDescription>
            </CardHeader>
            <form onSubmit={handleAddJob}>
              <CardContent className="space-y-4">
                {error && (
                  <div className="p-3 text-sm text-red-500 bg-red-50 dark:bg-red-950 rounded-md">
                    {error}
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="companyName">Company Name</Label>
                    <Input
                      id="companyName"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="Acme Corp"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="roleTitle">Role Title</Label>
                    <Input
                      id="roleTitle"
                      value={roleTitle}
                      onChange={(e) => setRoleTitle(e.target.value)}
                      placeholder="Senior Software Engineer"
                      required
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="jobDescription">Job Description</Label>
                  <textarea
                    id="jobDescription"
                    value={jobDescription}
                    onChange={(e) => setJobDescription(e.target.value)}
                    placeholder="Paste the full job description here..."
                    className="flex min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sourceUrl">Job Posting URL (optional)</Label>
                  <Input
                    id="sourceUrl"
                    type="url"
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    placeholder="https://..."
                  />
                </div>
              </CardContent>
              <CardFooter className="gap-2">
                <Button type="submit">Save Job</Button>
                <Button type="button" variant="outline" onClick={() => setShowAddForm(false)}>
                  Cancel
                </Button>
              </CardFooter>
            </form>
          </Card>
        )}

        {/* Generated Draft Modal */}
        {generatedDraft && (
          <Card className="mb-8 border-primary">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
                Generated Cover Letter
              </CardTitle>
              <CardDescription>
                Review and edit the AI-generated cover letter below
              </CardDescription>
            </CardHeader>
            <CardContent>
              <textarea
                value={generatedDraft.content}
                onChange={(e) => setGeneratedDraft({ ...generatedDraft, content: e.target.value })}
                className="flex min-h-[300px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </CardContent>
            <CardFooter className="gap-2">
              <Button
                onClick={async () => {
                  await agentApi.updateDraft(generatedDraft.draftId, generatedDraft.content)
                  alert("Draft saved!")
                }}
              >
                Save Draft
              </Button>
              <Button variant="outline" onClick={() => setGeneratedDraft(null)}>
                Close
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* Jobs List */}
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : jobs.length === 0 ? (
          <Card>
            <CardContent className="text-center py-12 text-muted-foreground">
              <Briefcase className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">No jobs saved yet</p>
              <p className="text-sm">Click "Add Job" to get started</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {jobs.map((job) => (
              <Card key={job.id}>
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <div>
                      <CardTitle className="text-lg">{job.role_title}</CardTitle>
                      <CardDescription>{job.company_name}</CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      {job.application_status && (
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[job.application_status] || ""}`}>
                          {job.application_status}
                        </span>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDeleteJob(job.id)}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {job.job_description.substring(0, 300)}...
                  </p>
                </CardContent>
                <CardFooter className="gap-2">
                  <Button
                    onClick={() => handleGenerateCoverLetter(job)}
                    disabled={generating === job.id}
                  >
                    {generating === job.id ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4 mr-2" />
                        Generate Cover Letter
                      </>
                    )}
                  </Button>
                  {!job.has_application && (
                    <Button variant="outline" onClick={() => handleMarkApplied(job)}>
                      <CheckCircle className="h-4 w-4 mr-2" />
                      Mark Applied
                    </Button>
                  )}
                  {job.source_url && (
                    <Button variant="ghost" asChild>
                      <a href={job.source_url} target="_blank" rel="noopener noreferrer">
                        <FileText className="h-4 w-4 mr-2" />
                        View Posting
                      </a>
                    </Button>
                  )}
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

"use client"

import { useState, useEffect } from "react"
import { useAuth } from "@/hooks/useAuth"
import { jobsApi, applicationsApi, agentApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import {
  Plus,
  Briefcase,
  Calendar,
  Mail,
  ArrowRight,
  ArrowLeft,
  Loader2,
  MoreVertical,
  Edit,
  Trash2,
  Sparkles,
  CalendarCheck,
  Send,
} from "lucide-react"

type ApplicationStatus = "saved" | "applied" | "interview" | "offer" | "rejected" | "withdrawn"

const STATUS_CONFIG: Record<ApplicationStatus, { label: string; color: string; icon: React.ReactNode }> = {
  saved: { label: "Saved", color: "bg-gray-500", icon: <Briefcase className="h-4 w-4" /> },
  applied: { label: "Applied", color: "bg-blue-500", icon: <Mail className="h-4 w-4" /> },
  interview: { label: "Interviewing", color: "bg-purple-500", icon: <Calendar className="h-4 w-4" /> },
  offer: { label: "Offer", color: "bg-green-500", icon: <Sparkles className="h-4 w-4" /> },
  rejected: { label: "Rejected", color: "bg-red-500", icon: <Trash2 className="h-4 w-4" /> },
  withdrawn: { label: "Withdrawn", color: "bg-orange-500", icon: <ArrowLeft className="h-4 w-4" /> },
}

const STATUS_ORDER: ApplicationStatus[] = ["saved", "applied", "interview", "offer", "rejected", "withdrawn"]

interface Application {
  id: string
  job_id: string
  status: ApplicationStatus
  applied_at: string | null
  follow_up_date: string | null
  notes: string | null
  created_at: string
  job?: {
    id: string
    company_name: string
    role_title: string
    job_description: string
  }
}

interface ColumnProps {
  status: ApplicationStatus
  applications: Application[]
  onMove: (appId: string, newStatus: ApplicationStatus) => void
  onEdit: (app: Application) => void
  onGenerateDraft: (app: Application) => void
  onScheduleInterview: (app: Application) => void
  onGenerateFollowUp: (app: Application) => void
}

function Column({
  status,
  applications,
  onMove,
  onEdit,
  onGenerateDraft,
  onScheduleInterview,
  onGenerateFollowUp,
}: ColumnProps) {
  const config = STATUS_CONFIG[status]

  return (
    <div className="flex flex-col min-w-[300px] max-w-[300px] bg-muted/50 rounded-lg">
      {/* Column header */}
      <div className="p-4 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={cn("w-2 h-2 rounded-full", config.color)} />
          <h3 className="font-semibold text-sm">{config.label}</h3>
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            {applications.length}
          </span>
        </div>
      </div>

      {/* Applications */}
      <ScrollArea className="flex-1 p-2 space-y-2">
        {applications.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground text-sm">
            Drop here
          </div>
        ) : (
          applications.map((app) => (
            <ApplicationCard
              key={app.id}
              app={app}
              onMove={onMove}
              onEdit={onEdit}
              onGenerateDraft={onGenerateDraft}
              onScheduleInterview={onScheduleInterview}
              onGenerateFollowUp={onGenerateFollowUp}
            />
          ))
        )}
      </ScrollArea>
    </div>
  )
}

interface ApplicationCardProps {
  app: Application
  onMove: (appId: string, newStatus: ApplicationStatus) => void
  onEdit: (app: Application) => void
  onGenerateDraft: (app: Application) => void
  onScheduleInterview: (app: Application) => void
  onGenerateFollowUp: (app: Application) => void
}

function ApplicationCard({
  app,
  onMove,
  onEdit,
  onGenerateDraft,
  onScheduleInterview,
  onGenerateFollowUp,
}: ApplicationCardProps) {
  const job = app.job
  const [showMenu, setShowMenu] = useState(false)

  if (!job) return null

  const currentStatusIndex = STATUS_ORDER.indexOf(app.status)

  return (
    <Card className="relative">
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-medium text-sm truncate">{job.role_title}</h4>
            </div>
            <p className="text-sm text-muted-foreground truncate">{job.company_name}</p>

            {app.applied_at && (
              <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                Applied: {new Date(app.applied_at).toLocaleDateString()}
              </p>
            )}

            {app.follow_up_date && (
              <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                <CalendarCheck className="h-3 w-3" />
                Follow up: {new Date(app.follow_up_date).toLocaleDateString()}
              </p>
            )}

            {app.notes && (
              <p className="text-xs text-muted-foreground mt-2 line-clamp-2">{app.notes}</p>
            )}
          </div>

          {/* Menu button */}
          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 p-0"
              onClick={() => setShowMenu(!showMenu)}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>

            {showMenu && (
              <div className="absolute right-0 top-full mt-1 z-10 bg-background border rounded-lg shadow-lg min-w-[160px] py-1">
                <button
                  className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2"
                  onClick={() => { onEdit(app); setShowMenu(false); }}
                >
                  <Edit className="h-3 w-3" /> Edit
                </button>
                {currentStatusIndex > 0 && (
                  <button
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2"
                    onClick={() => { onMove(app.id, STATUS_ORDER[currentStatusIndex - 1]); setShowMenu(false); }}
                  >
                    <ArrowLeft className="h-3 w-3" /> Move Back
                  </button>
                )}
                {currentStatusIndex < STATUS_ORDER.length - 1 && (
                  <button
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2"
                    onClick={() => { onMove(app.id, STATUS_ORDER[currentStatusIndex + 1]); setShowMenu(false); }}
                  >
                    <ArrowRight className="h-3 w-3" /> Move Forward
                  </button>
                )}
                <hr className="my-1" />
                <button
                  className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2"
                  onClick={() => { onGenerateDraft(app); setShowMenu(false); }}
                >
                  <Sparkles className="h-3 w-3" /> Generate Cover Letter
                </button>
                {app.status === "interview" && (
                  <button
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2"
                    onClick={() => { onScheduleInterview(app); setShowMenu(false); }}
                  >
                    <Calendar className="h-3 w-3" /> Schedule Interview
                  </button>
                )}
                {app.status === "applied" && (
                  <button
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2"
                    onClick={() => { onGenerateFollowUp(app); setShowMenu(false); }}
                  >
                    <Mail className="h-3 w-3" /> Generate Follow-up
                  </button>
                )}
                <hr className="my-1" />
                <button
                  className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2 text-red-600"
                  onClick={() => { /* Delete action */ setShowMenu(false); }}
                >
                  <Trash2 className="h-3 w-3" /> Delete
                </button>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function ApplicationTracker() {
  const { user } = useAuth()
  const [applications, setApplications] = useState<Application[]>([])
  const [jobs, setJobs] = useState<Array<{ id: string; company_name: string; role_title: string }>>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newApp, setNewApp] = useState({ job_id: "", status: "saved" as ApplicationStatus, notes: "" })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [appsRes, jobsRes] = await Promise.all([
        applicationsApi.list(),
        jobsApi.list(),
      ])

      if (appsRes.data) {
        setApplications(appsRes.data.applications as Application[])
      }
      if (jobsRes.data) {
        setJobs(jobsRes.data.jobs as Array<{ id: string; company_name: string; role_title: string }>)
      }
    } catch (error) {
      console.error("Failed to load data:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleMove = async (appId: string, newStatus: ApplicationStatus) => {
    try {
      await applicationsApi.update(appId, { status: newStatus })
      setApplications((prev) =>
        prev.map((app) => (app.id === appId ? { ...app, status: newStatus } : app))
      )
    } catch (error) {
      console.error("Failed to update status:", error)
    }
  }

  const handleCreateApplication = async () => {
    try {
      const res = await applicationsApi.create(newApp)
      if (res.data) {
        setApplications((prev) => [...prev, res.data as Application])
        setShowAddModal(false)
        setNewApp({ job_id: "", status: "saved", notes: "" })
      }
    } catch (error) {
      console.error("Failed to create application:", error)
    }
  }

  const handleGenerateDraft = async (app: Application) => {
    // Navigate to cover letter editor
    // This would need routing - for now just generate
    try {
      const res = await agentApi.generateDraft(app.job_id, true)
      if (res.data) {
        alert(`Cover letter generated! Draft ID: ${res.data.draft_id}`)
      }
    } catch (error) {
      console.error("Failed to generate draft:", error)
    }
  }

  const handleScheduleInterview = (app: Application) => {
    // Open interview scheduling modal
    const date = prompt("Interview date/time (ISO format):")
    if (date && app.job) {
      agentApi.scheduleInterview({
        company_name: app.job.company_name,
        role_title: app.job.role_title,
        start_time: date,
        duration_minutes: 60,
      }).then(() => alert("Interview scheduled!"))
    }
  }

  const handleGenerateFollowUp = async (app: Application) => {
    try {
      const res = await agentApi.generateFollowUp(app.id)
      if (res.data) {
        alert(`Follow-up email generated! Draft ID: ${res.data.draft_id}`)
      }
    } catch (error) {
      console.error("Failed to generate follow-up:", error)
    }
  }

  const handleEdit = (app: Application) => {
    // Open edit modal
    const notes = prompt("Notes:", app.notes || "")
    if (notes !== null) {
      applicationsApi.update(app.id, { notes }).then(() => {
        setApplications((prev) =>
          prev.map((a) => (a.id === app.id ? { ...a, notes } : a))
        )
      })
    }
  }

  // Group applications by status
  const columns = STATUS_ORDER.map((status) => ({
    status,
    apps: applications.filter((a) => a.status === status),
  }))

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h1 className="text-xl font-semibold">Application Tracker</h1>
          <p className="text-sm text-muted-foreground">
            {applications.length} applications across {columns.filter(c => c.apps.length > 0).length} stages
          </p>
        </div>
        <Button onClick={() => setShowAddModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Application
        </Button>
      </div>

      {/* Kanban Board */}
      <ScrollArea className="flex-1 p-4">
        <div className="flex gap-4 min-w-max pb-4">
          {columns.map(({ status, apps }) => (
            <Column
              key={status}
              status={status}
              applications={apps}
              onMove={handleMove}
              onEdit={handleEdit}
              onGenerateDraft={handleGenerateDraft}
              onScheduleInterview={handleScheduleInterview}
              onGenerateFollowUp={handleGenerateFollowUp}
            />
          ))}
        </div>
      </ScrollArea>

      {/* Add Application Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Add Application</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Job</label>
                <select
                  value={newApp.job_id}
                  onChange={(e) => setNewApp({ ...newApp, job_id: e.target.value })}
                  className="w-full p-2 border rounded-md"
                  required
                >
                  <option value="">Select a job...</option>
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.role_title} at {job.company_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Status</label>
                <select
                  value={newApp.status}
                  onChange={(e) => setNewApp({ ...newApp, status: e.target.value as ApplicationStatus })}
                  className="w-full p-2 border rounded-md"
                >
                  {STATUS_ORDER.map((s) => (
                    <option key={s} value={s}>{STATUS_CONFIG[s].label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Notes</label>
                <textarea
                  value={newApp.notes}
                  onChange={(e) => setNewApp({ ...newApp, notes: e.target.value })}
                  className="w-full p-2 border rounded-md min-h-[80px]"
                  rows={3}
                />
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setShowAddModal(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreateApplication}>
                  Add Application
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
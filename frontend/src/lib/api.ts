/**
 * API client for communicating with the FastAPI backend.
 * Handles authentication tokens and error responses.
 */

import { API_URL } from "./utils"

interface ApiResponse<T> {
  data?: T
  error?: string
}

/**
 * Fetch wrapper that includes auth token and handles errors.
 */
export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = `${API_URL}${endpoint}`

  // Get token from localStorage (client-side only)
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        error: errorData.detail || `HTTP ${response.status}: ${response.statusText}`,
      }
    }

    // Handle empty responses
    const text = await response.text()
    const data = text ? JSON.parse(text) : null

    return { data }
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "Network error",
    }
  }
}

/**
 * Auth API endpoints
 */
export const authApi = {
  signup: async (email: string, password: string, name?: string) => {
    return apiFetch<{ access_token: string; refresh_token: string }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    })
  },

  login: async (email: string, password: string) => {
    return apiFetch<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
  },

  getMe: async () => {
    return apiFetch<{ id: string; email: string; name: string | null }>("/auth/me")
  },
}

/**
 * Documents API endpoints
 */
export const documentsApi = {
  list: async (docType?: string) => {
    const params = docType ? `?doc_type=${docType}` : ""
    return apiFetch<{ documents: Array<{ id: string; doc_type: string; filename: string; uploaded_at: string }> }>(
      `/documents${params}`
    )
  },

  upload: async (file: File, docType: string): Promise<ApiResponse<{ id: string; doc_type: string; filename: string; uploaded_at: string }>> => {
    const formData = new FormData()
    formData.append("file", file)
    formData.append("doc_type", docType)

    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null

    try {
      const response = await fetch(`${API_URL}/documents/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        return { error: errorData.detail || "Upload failed" }
      }

      const data = await response.json()
      return { data }
    } catch (error) {
      return { error: error instanceof Error ? error.message : "Network error" }
    }
  },

  delete: async (documentId: string) => {
    return apiFetch<void>(`/documents/${documentId}`, {
      method: "DELETE",
    })
  },
}

/**
 * Jobs API endpoints
 */
export const jobsApi = {
  list: async (skip = 0, limit = 50) => {
    return apiFetch<{ jobs: Array<{
      id: string
      company_name: string
      role_title: string
      job_description: string
      source_url: string | null
      created_at: string
      has_application: boolean
      application_status: string | null
    }>; total: number }>(`/jobs?skip=${skip}&limit=${limit}`)
  },

  get: async (jobId: string) => {
    return apiFetch<{
      id: string
      company_name: string
      role_title: string
      job_description: string
      source_url: string | null
      created_at: string
      has_application: boolean
      application_status: string | null
    }>(`/jobs/${jobId}`)
  },

  create: async (data: {
    company_name: string
    role_title: string
    job_description: string
    source_url?: string
  }) => {
    return apiFetch<{
      id: string
      company_name: string
      role_title: string
      job_description: string
      source_url: string | null
      created_at: string
    }>("/jobs", {
      method: "POST",
      body: JSON.stringify(data),
    })
  },

  delete: async (jobId: string) => {
    return apiFetch<void>(`/jobs/${jobId}`, { method: "DELETE" })
  },
}

/**
 * Applications API endpoints
 */
export const applicationsApi = {
  list: async (status?: string) => {
    const params = status ? `?status_filter=${status}` : ""
    return apiFetch<{ applications: Array<{
      id: string
      job_id: string
      status: string
      applied_at: string | null
      follow_up_date: string | null
      notes: string | null
      created_at: string
    }> }>(`/jobs/applications${params}`)
  },

  create: async (data: { job_id: string; status?: string; notes?: string }) => {
    return apiFetch<{
      id: string
      job_id: string
      status: string
      applied_at: string | null
      follow_up_date: string | null
      notes: string | null
      created_at: string
    }>("/jobs/applications", {
      method: "POST",
      body: JSON.stringify(data),
    })
  },

  update: async (applicationId: string, data: {
    status?: string
    notes?: string
    follow_up_date?: string
  }) => {
    const params = new URLSearchParams()
    if (data.status) params.append("status", data.status)
    if (data.notes) params.append("notes", data.notes)
    if (data.follow_up_date) params.append("follow_up_date", data.follow_up_date)

    return apiFetch<{
      id: string
      job_id: string
      status: string
      applied_at: string | null
      follow_up_date: string | null
      notes: string | null
      created_at: string
    }>(`/jobs/applications/${applicationId}?${params.toString()}`, {
      method: "PATCH",
    })
  },
}

/**
 * Agent API endpoints
 */
export const agentApi = {
  generateDraft: async (jobId: string, includeCritique = false) => {
    return apiFetch<{
      draft_id: string
      content: string
      retrieved_chunk_ids: string[]
      requirements: Record<string, unknown>
      critique: Record<string, unknown> | null
    }>("/agent/draft", {
      method: "POST",
      body: JSON.stringify({
        job_id: jobId,
        draft_type: "cover_letter",
        include_critique: includeCritique,
      }),
    })
  },

  getDraft: async (draftId: string) => {
    return apiFetch<{
      id: string
      draft_type: string
      content: string
      retrieved_chunk_ids: string[]
      user_edited_content: string | null
      created_at: string
    }>(`/agent/drafts/${draftId}`)
  },

  updateDraft: async (draftId: string, editedContent: string) => {
    const params = new URLSearchParams({ edited_content: editedContent })
    return apiFetch<{
      id: string
      message: string
    }>(`/agent/drafts/${draftId}?${params.toString()}`, {
      method: "PATCH",
    })
  },

  // Agent chat with tools
  chat: async (message: string, conversationHistory?: Array<{ role: string; content: string }>) => {
    return apiFetch<{
      response: string
      tool_calls: Array<{
        tool: string
        parameters: Record<string, unknown>
        result: Record<string, unknown>
        error: string | null
      }>
      state: string
      error: string | null
    }>("/agent/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_history: conversationHistory,
      }),
    })
  },

  // Calendar
  scheduleInterview: async (data: {
    company_name: string
    role_title: string
    start_time: string
    duration_minutes?: number
    location?: string
    interviewer_emails?: string[]
  }) => {
    return apiFetch<{
      event_id: string
      title: string
      start_time: string
      end_time: string
      location: string | null
    }>("/agent/schedule-interview", {
      method: "POST",
      body: JSON.stringify(data),
    })
  },

  getUpcomingEvents: async (daysAhead = 7, eventType?: string) => {
    const params = new URLSearchParams({ days_ahead: daysAhead.toString() })
    if (eventType) params.append("event_type", eventType)
    return apiFetch<{ events: Array<{
      id: string
      title: string
      start_time: string
      end_time: string
      location: string | null
      event_type: string
    }> }>(`/agent/events/upcoming?${params.toString()}`)
  },

  // Email drafts
  generateFollowUp: async (applicationId: string) => {
    return apiFetch<{
      draft_id: string
      subject: string
      body: string
      email_type: string
    }>(`/agent/email/follow-up/${applicationId}`, { method: "POST" })
  },

  generateThankYou: async (data: {
    application_id: string
    interviewer_name: string
    interview_date: string
    topics_discussed?: string
    what_excited_you?: string
  }) => {
    return apiFetch<{
      draft_id: string
      subject: string
      body: string
      email_type: string
    }>("/agent/email/thank-you", {
      method: "POST",
      body: JSON.stringify(data),
    })
  },

  generateNetworking: async (data: {
    recipient_name: string
    recipient_role: string
    company_name: string
    your_background: string
    why_reaching_out: string
    shared_connection?: string
  }) => {
    return apiFetch<{
      draft_id: string
      subject: string
      body: string
      email_type: string
    }>("/agent/email/networking", {
      method: "POST",
      body: JSON.stringify(data),
    })
  },
}

/**
 * Memory API endpoints
 */
export const memoryApi = {
  getChatHistory: async (sessionId: string, limit = 20) => {
    return apiFetch<{
      session_id: string
      messages: Array<{
        id: string
        role: string
        content: string
        tool_calls: unknown | null
        tool_call_id: string | null
        created_at: string
      }>
    }>(`/memory/chat/${sessionId}?limit=${limit}`)
  },

  clearChatHistory: async (sessionId: string) => {
    return apiFetch<{ deleted: number }>(`/memory/chat/${sessionId}`, { method: "DELETE" })
  },

  getStylePreferences: async (limit = 20) => {
    return apiFetch<{
      preferences: Array<{
        id: string
        preference_text: string
        source_draft_id: string | null
        created_at: string
      }>
    }>(`/memory/style?limit=${limit}`)
  },

  updateStyleFromEdit: async (draftId: string, originalContent: string, editedContent: string) => {
    return apiFetch<{
      updated: boolean
      preference_text: string | null
    }>("/memory/style/update", {
      method: "POST",
      body: JSON.stringify({
        draft_id: draftId,
        original_content: originalContent,
        edited_content: editedContent,
      }),
    })
  },

  getStyleContext: async (jobDescription: string) => {
    return apiFetch<{ context: string }>("/memory/style/context", {
      method: "POST",
      body: JSON.stringify({ job_description: jobDescription }),
    })
  },
}

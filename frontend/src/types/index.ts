/**
 * Frontend TypeScript types
 */

export interface User {
  id: string
  email: string
  name: string | null
}

export interface Document {
  id: string
  doc_type: string
  filename: string
  uploaded_at: string
}

export interface Job {
  id: string
  company_name: string
  role_title: string
  job_description: string
  source_url: string | null
  created_at: string
}

export interface Application {
  id: string
  job_id: string
  status: "saved" | "applied" | "interview" | "offer" | "rejected"
  applied_at: string | null
  follow_up_date: string | null
  notes: string | null
}

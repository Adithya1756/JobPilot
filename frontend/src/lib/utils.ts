import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * API base URL - points to FastAPI backend
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

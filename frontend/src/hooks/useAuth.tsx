"use client"

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react"
import { authApi } from "@/lib/api"

interface User {
  id: string
  email: string
  name: string | null
}

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<{ error?: string }>
  signup: (email: string, password: string, name?: string) => Promise<{ error?: string }>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // Check for existing token on mount
  useEffect(() => {
    const token = localStorage.getItem("token")
    if (token) {
      // Verify token by fetching user info
      authApi.getMe().then((result) => {
        if (result.data) {
          setUser(result.data)
        } else {
          // Token invalid, clear it
          localStorage.removeItem("token")
          localStorage.removeItem("refreshToken")
        }
        setLoading(false)
      })
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (email: string, password: string) => {
    const result = await authApi.login(email, password)
    if (result.data) {
      localStorage.setItem("token", result.data.access_token)
      localStorage.setItem("refreshToken", result.data.refresh_token)
      // Fetch user info
      const userResult = await authApi.getMe()
      if (userResult.data) {
        setUser(userResult.data)
      }
      return {}
    }
    return { error: result.error || "Login failed" }
  }

  const signup = async (email: string, password: string, name?: string) => {
    const result = await authApi.signup(email, password, name)
    if (result.data) {
      localStorage.setItem("token", result.data.access_token)
      localStorage.setItem("refreshToken", result.data.refresh_token)
      // Fetch user info
      const userResult = await authApi.getMe()
      if (userResult.data) {
        setUser(userResult.data)
      }
      return {}
    }
    return { error: result.error || "Signup failed" }
  }

  const logout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("refreshToken")
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}

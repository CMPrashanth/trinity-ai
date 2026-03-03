import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { authAPI, User } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();

  // Initialize auth state from localStorage
  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem("token");
      const storedUser = localStorage.getItem("user");

      if (storedToken && storedUser) {
        setToken(storedToken);
        try {
          // Verify token is still valid by fetching current user
          const currentUser = await authAPI.getCurrentUser();
          setUser(currentUser);
          localStorage.setItem("user", JSON.stringify(currentUser));
        } catch (error) {
          // Token is invalid, clear storage
          localStorage.removeItem("token");
          localStorage.removeItem("user");
          setToken(null);
          setUser(null);
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    try {
      setIsLoading(true);
      
      const tokenResponse = await authAPI.login({ email, password });
      const accessToken = tokenResponse.access_token;

      localStorage.setItem("token", accessToken);
      setToken(accessToken);

      const userData = await authAPI.getCurrentUser();
      setUser(userData);
      localStorage.setItem("user", JSON.stringify(userData));

      toast({
        title: "Login Successful",
        description: `Welcome back, ${userData.name}!`,
      });
    } catch (error: any) {
      console.error("Login error:", error);
      let errorMessage = "An unexpected error occurred during login.";

      const detail = error.response?.data?.detail;

      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (Array.isArray(detail)) {
        // Handle array of Pydantic validation errors
        errorMessage = detail.map(err => {
          const location = err.loc?.join(' > ') || 'error';
          return `${location}: ${err.msg}`;
        }).join("\n");
      } else if (typeof detail === 'object' && detail !== null) {
        // Handle single Pydantic validation error object
        const location = detail.loc?.join(' > ') || 'error';
        errorMessage = `${location}: ${detail.msg}`;
      }

      toast({
        title: "Login Failed",
        description: errorMessage,
        variant: "destructive",
      });
      // We throw the error so the component can stop its loading state
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, password: string, name: string) => {
    try {
      setIsLoading(true);

      await authAPI.register({ email, password, name });

      toast({
        title: "Account Created",
        description: "Please log in with your new credentials.",
      });
      
      // Optionally, you can automatically log the user in after registration
      // await login(email, password);

    } catch (error: any) {
      console.error("Registration error:", error);
      let errorMessage = "An unexpected error occurred during registration.";

      const detail = error.response?.data?.detail;

      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (Array.isArray(detail)) {
        errorMessage = detail.map(err => `${err.loc?.join(' > ') || 'error'}: ${err.msg}`).join("\n");
      } else if (typeof detail === 'object' && detail !== null) {
        const location = detail.loc?.join(' > ') || 'error';
        errorMessage = `${location}: ${detail.msg}`;
      }
      
      toast({
        title: "Registration Failed",
        description: errorMessage,
        variant: "destructive",
      });
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    authAPI.logout();
    setUser(null);
    setToken(null);
    toast({
      title: "Logged Out",
      description: "You have been successfully logged out.",
    });
  };

  const value: AuthContextType = {
    user,
    token,
    isLoading,
    isAuthenticated: !!user && !!token,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

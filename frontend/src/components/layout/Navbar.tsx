import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { 
  Shield, 
  Menu, 
  X, 
  Activity, 
  Target, 
  Network, 
  FileText, 
  Settings,
  AlertTriangle,
  LogOut,
  User
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { agentAPI } from "@/lib/api";

const navLinks = [
  { href: "/", label: "Dashboard", icon: Activity },
  { href: "/scan", label: "New Scan", icon: Target },
  { href: "/graph", label: "Attack Graph", icon: Network },
  { href: "/vulnerabilities", label: "Findings", icon: AlertTriangle },
  { href: "/logs", label: "Activity Logs", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, isAuthenticated } = useAuth();
  
  // Fetch agent status
  const { data: agentStatus } = useQuery({
    queryKey: ["agentStatus"],
    queryFn: agentAPI.getStatus,
    refetchInterval: 10000, // Refresh every 10 seconds
    enabled: isAuthenticated, // Only fetch when authenticated
  });

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/50 bg-background/80 backdrop-blur-xl">
      <nav className="container mx-auto flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3 group">
          <div className="relative">
            <Shield className="h-8 w-8 text-primary transition-all duration-300 group-hover:text-glow" />
            <div className="absolute inset-0 bg-primary/20 blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-lg tracking-tight text-foreground">
              Trinity<span className="text-primary">Agent</span>
            </span>
            <span className="text-[10px] text-muted-foreground font-mono uppercase tracking-widest">
              Autonomous Pentesting
            </span>
          </div>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden lg:flex items-center gap-1">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const isActive = location.pathname === link.href;
            return (
              <Link
                key={link.href}
                to={link.href}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/30"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                )}
              >
                <Icon className="h-4 w-4" />
                {link.label}
              </Link>
            );
          })}
        </div>

            {/* Status Indicator + Auth */}
        <div className="hidden lg:flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted border border-border">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
            </span>
            <span className="text-xs font-mono text-primary">AGENT ONLINE</span>
          </div>
          {isAuthenticated ? (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted border border-border">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">{user?.name || user?.email}</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  logout();
                  navigate("/auth");
                }}
              >
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          ) : (
            <Link to="/auth">
              <Button variant="outline" size="sm">
                Sign In
              </Button>
            </Link>
          )}
        </div>

        {/* Mobile Menu Button */}
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle navigation menu"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>
      </nav>

      {/* Mobile Navigation */}
      {mobileOpen && (
        <div className="lg:hidden border-t border-border bg-background/95 backdrop-blur-xl animate-fade-up">
          <div className="container mx-auto px-4 py-4 space-y-2">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = location.pathname === link.href;
              return (
                <Link
                  key={link.href}
                  to={link.href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 rounded-lg text-base font-medium transition-all",
                    isActive
                      ? "bg-primary/10 text-primary border border-primary/30"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  )}
                >
                  <Icon className="h-5 w-5" />
                  {link.label}
                </Link>
              );
            })}
            <div className="pt-4 border-t border-border space-y-2">
              {/* Agent Status for Mobile */}
              <div className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-md border",
                agentStatus?.status === "online" ? "bg-primary/10 border-primary/30" :
                agentStatus?.status === "degraded" ? "bg-warning/10 border-warning/30" :
                "bg-muted border-border"
              )}>
                <span className="relative flex h-2 w-2">
                  {agentStatus?.status === "online" && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                  )}
                  <span className={cn(
                    "relative inline-flex rounded-full h-2 w-2",
                    agentStatus?.status === "online" ? "bg-primary" :
                    agentStatus?.status === "degraded" ? "bg-warning" :
                    "bg-destructive"
                  )}></span>
                </span>
                <span className={cn(
                  "text-xs font-mono",
                  agentStatus?.status === "online" ? "text-primary" :
                  agentStatus?.status === "degraded" ? "text-warning" :
                  "text-destructive"
                )}>
                  AGENT {agentStatus?.status?.toUpperCase() || "OFFLINE"}
                </span>
              </div>

              {isAuthenticated ? (
                <>
                  <div className="flex items-center gap-2 px-4 py-2 rounded-md bg-muted border border-border">
                    <User className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">{user?.name || user?.email}</span>
                  </div>
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => {
                      logout();
                      navigate("/auth");
                      setMobileOpen(false);
                    }}
                  >
                    <LogOut className="h-4 w-4 mr-2" />
                    Logout
                  </Button>
                </>
              ) : (
                <Link to="/auth" onClick={() => setMobileOpen(false)}>
                  <Button variant="outline" className="w-full">
                    Sign In
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
}

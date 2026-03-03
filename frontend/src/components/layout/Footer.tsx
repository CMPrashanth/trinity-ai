import { Shield, Github, BookOpen, MessageSquare } from "lucide-react";
import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="border-t border-border bg-background/50">
      <div className="container mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <Shield className="h-6 w-6 text-primary" />
              <span className="font-bold text-lg">
                Trinity<span className="text-primary">Agent</span>
              </span>
            </div>
            <p className="text-muted-foreground text-sm max-w-md mb-4">
              A stateful autonomous pentesting agent featuring neuro-symbolic AI, 
              graph-based attack path memory, and self-healing code execution. 
              Built for enterprise security assessments.
            </p>
            <p className="text-xs text-muted-foreground font-mono">
              Final Year Engineering Project © 2024
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="font-semibold mb-4 text-foreground">Platform</h4>
            <ul className="space-y-2">
              <li>
                <Link to="/" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link to="/scan" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                  Start Scan
                </Link>
              </li>
              <li>
                <Link to="/graph" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                  Attack Graph
                </Link>
              </li>
              <li>
                <Link to="/vulnerabilities" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                  Vulnerabilities
                </Link>
              </li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="font-semibold mb-4 text-foreground">Resources</h4>
            <ul className="space-y-2">
              <li>
                <a 
                  href="#" 
                  className="text-sm text-muted-foreground hover:text-primary transition-colors flex items-center gap-2"
                >
                  <BookOpen className="h-4 w-4" />
                  Documentation
                </a>
              </li>
              <li>
                <a 
                  href="#" 
                  className="text-sm text-muted-foreground hover:text-primary transition-colors flex items-center gap-2"
                >
                  <Github className="h-4 w-4" />
                  Source Code
                </a>
              </li>
              <li>
                <a 
                  href="#" 
                  className="text-sm text-muted-foreground hover:text-primary transition-colors flex items-center gap-2"
                >
                  <MessageSquare className="h-4 w-4" />
                  Report Issue
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 pt-8 border-t border-border flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <span className="text-xs text-muted-foreground">
              Powered by LangGraph + Neo4j + ChromaDB
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-primary animate-pulse"></span>
              System Status: Operational
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}

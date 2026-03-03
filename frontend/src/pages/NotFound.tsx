import { useLocation, Link } from "react-router-dom";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Shield, Home, AlertTriangle } from "lucide-react";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background grid-pattern">
      <div className="text-center px-4">
        <div className="inline-flex items-center justify-center mb-6">
          <div className="relative">
            <Shield className="h-20 w-20 text-muted-foreground" />
            <AlertTriangle className="h-8 w-8 text-warning absolute bottom-0 right-0" />
          </div>
        </div>
        <h1 className="text-6xl font-bold text-primary mb-4 font-mono">404</h1>
        <p className="text-xl text-muted-foreground mb-2">Target Not Found</p>
        <p className="text-sm text-muted-foreground mb-8 font-mono">
          Route "{location.pathname}" is outside the allowed scope.
        </p>
        <Link to="/">
          <Button variant="hero" size="lg">
            <Home className="h-5 w-5" />
            Return to Dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
};

export default NotFound;

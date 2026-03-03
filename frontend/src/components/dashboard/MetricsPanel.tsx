import { Shield, AlertTriangle, Target, Activity, TrendingUp, Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { vulnerabilitiesAPI, scansAPI } from "@/lib/api";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  variant?: "default" | "critical" | "warning" | "success";
  className?: string;
}

function MetricCard({ 
  title, 
  value, 
  subtitle, 
  icon: Icon, 
  trend, 
  variant = "default",
  className 
}: MetricCardProps) {
  const variantStyles = {
    default: "border-border",
    critical: "border-destructive/30 bg-destructive/5",
    warning: "border-warning/30 bg-warning/5",
    success: "border-primary/30 bg-primary/5",
  };

  const iconStyles = {
    default: "text-muted-foreground",
    critical: "text-destructive",
    warning: "text-warning",
    success: "text-primary",
  };

  return (
    <Card className={cn("hover-glow transition-all duration-300", variantStyles[variant], className)}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground font-medium">{title}</p>
            <p className="text-3xl font-bold tracking-tight">{value}</p>
            {subtitle && (
              <p className="text-xs text-muted-foreground">{subtitle}</p>
            )}
            {trend && (
              <div className={cn(
                "flex items-center gap-1 text-xs font-medium",
                trend.isPositive ? "text-primary" : "text-destructive"
              )}>
                <TrendingUp className={cn("h-3 w-3", !trend.isPositive && "rotate-180")} />
                {trend.value}% from last scan
              </div>
            )}
          </div>
          <div className={cn("p-3 rounded-lg bg-muted/50", iconStyles[variant])}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function MetricsPanel() {
  const { data: vulnStats } = useQuery({
    queryKey: ["vulnerabilityStats"],
    queryFn: () => vulnerabilitiesAPI.stats(),
  });

  const { data: scansData } = useQuery({
    queryKey: ["scans"],
    queryFn: () => scansAPI.list({ limit: 100 }),
  });

  const scans = scansData?.scans ?? [];
  const activeScans = scans.filter(s => s.status === "running" || s.status === "queued").length;
  const completedScans = scans.filter(s => s.status === "completed").length;
  const totalVulns = vulnStats?.total || 0;
  const criticalVulns = vulnStats?.by_severity?.critical || 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard
        title="Critical Vulnerabilities"
        value={criticalVulns}
        subtitle="Requires immediate attention"
        icon={AlertTriangle}
        variant="critical"
      />
      <MetricCard
        title="Active Scans"
        value={activeScans}
        subtitle="Running or queued"
        icon={Target}
        variant="default"
      />
      <MetricCard
        title="Total Vulnerabilities"
        value={totalVulns}
        subtitle="All findings"
        icon={Shield}
        variant={totalVulns > 0 ? "warning" : "success"}
      />
      <MetricCard
        title="Completed Scans"
        value={completedScans}
        subtitle="Total scans finished"
        icon={Activity}
        variant="default"
      />
    </div>
  );
}

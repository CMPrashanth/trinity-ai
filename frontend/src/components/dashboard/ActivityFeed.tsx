import { Play, CheckCircle2, AlertCircle, XCircle, RefreshCw, Shield, Database, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { dashboardAPI, DashboardActivityItem } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";

const activityConfig: Record<string, { icon: React.ElementType; color: string; bgColor: string; borderColor: string }> = {
  scan_start: { icon: Play, color: "text-accent", bgColor: "bg-accent/10", borderColor: "border-accent/30" },
  vuln_found: { icon: AlertCircle, color: "text-destructive", bgColor: "bg-destructive/10", borderColor: "border-destructive/30" },
  scan_complete: { icon: CheckCircle2, color: "text-primary", bgColor: "bg-primary/10", borderColor: "border-primary/30" },
  error: { icon: XCircle, color: "text-destructive", bgColor: "bg-destructive/10", borderColor: "border-destructive/30" },
  retry: { icon: RefreshCw, color: "text-warning", bgColor: "bg-warning/10", borderColor: "border-warning/30" },
  circuit_break: { icon: Shield, color: "text-destructive", bgColor: "bg-destructive/10", borderColor: "border-destructive/30" },
};

export function ActivityFeed() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboardActivity"],
    queryFn: () => dashboardAPI.activity({ limit: 5 }),
    refetchInterval: 10000,
  });

  const activities = data?.activities ?? [];

  return (
    <Card variant="glow" className="h-full">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg"><Database className="h-5 w-5 text-primary" />Agent Activity</CardTitle>
          <Badge variant="terminal" className="text-xs">Live Feed</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 max-h-[500px] overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-6 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : activities.length === 0 ? (
          <div className="flex items-center justify-center py-6 text-muted-foreground text-sm">
            No recent activity.
          </div>
        ) : (
          activities.map((activity: DashboardActivityItem, index) => {
            const config = activityConfig[activity.type] ?? activityConfig.scan_start;
            const Icon = config.icon;
            const timestampLabel = formatDistanceToNow(new Date(activity.timestamp), { addSuffix: true });
            return (
              <div
                key={activity.id}
                className={cn(
                  "flex gap-3 p-3 rounded-lg border transition-all duration-300 hover:bg-muted/50 animate-fade-up",
                  config.bgColor,
                  config.borderColor
                )}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className={cn("mt-0.5 p-1.5 rounded-md", config.bgColor)}>
                  <Icon className={cn("h-4 w-4", config.color)} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-foreground">{activity.message}</p>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">{timestampLabel}</span>
                  </div>
                  {activity.target && <p className="text-xs font-mono text-primary mt-1">{activity.target}</p>}
                  {activity.details && <p className="text-xs text-muted-foreground mt-1 truncate">{activity.details}</p>}
                </div>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}

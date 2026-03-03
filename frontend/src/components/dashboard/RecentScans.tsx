import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Target, Clock, CheckCircle2, XCircle, Loader2, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { scansAPI, Scan } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";

const statusConfig: Record<string, { icon: React.ElementType; color: string; bgColor: string; label: string; animate?: boolean }> = {
  completed: { icon: CheckCircle2, color: "text-primary", bgColor: "bg-primary/10", label: "Completed" },
  running: { icon: Loader2, color: "text-accent", bgColor: "bg-accent/10", label: "Running", animate: true },
  failed: { icon: XCircle, color: "text-destructive", bgColor: "bg-destructive/10", label: "Failed" },
  queued: { icon: Clock, color: "text-muted-foreground", bgColor: "bg-muted", label: "Queued" },
  cancelled: { icon: XCircle, color: "text-muted-foreground", bgColor: "bg-muted", label: "Cancelled" },
};

export function RecentScans() {
  const { data, isLoading } = useQuery({
    queryKey: ["recentScans"],
    queryFn: () => scansAPI.list({ limit: 4 }),
    refetchInterval: 5000, // Refetch every 5 seconds for live updates
  });

  const scans: Scan[] = data?.scans ?? [];

  return (
    <Card variant="glow">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg"><Target className="h-5 w-5 text-accent" />Recent Scans</CardTitle>
          <Link to="/logs"><Button variant="ghost" size="sm" className="text-xs">View All<ChevronRight className="h-4 w-4 ml-1" /></Button></Link>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : scans.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <p className="text-sm">No scans yet. Start your first scan!</p>
          </div>
        ) : (
          scans.map((scan) => {
          const status = statusConfig[scan.status] || statusConfig.queued;
          const StatusIcon = status.icon;
          const findings = scan.findings || {};
          const totalFindings = Object.values(findings).reduce((a, b) => (a as number) + (b as number), 0) as number;
          const timeAgo = formatDistanceToNow(new Date(scan.start_time), { addSuffix: true });
          
          return (
            <div key={scan.scan_id} className="p-4 rounded-lg border border-border bg-card/50 hover:bg-muted/30 transition-all duration-200 cursor-pointer group">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <code className="text-sm font-mono text-primary">{scan.target}</code>
                    <Badge variant={scan.status === "completed" ? "success" : scan.status === "running" ? "info" : scan.status === "failed" ? "critical" : "secondary"} className="text-xs">
                      <StatusIcon className={cn("h-3 w-3 mr-1", status.animate && "animate-spin")} />{status.label}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mb-2">{scan.scan_profile}</p>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-muted-foreground flex items-center gap-1"><Clock className="h-3 w-3" />{timeAgo}</span>
                    {scan.progress > 0 && <span className="text-muted-foreground">Progress: {scan.progress}%</span>}
                  </div>
                </div>
                {totalFindings > 0 && typeof findings === 'object' && (
                  <div className="flex items-center gap-1.5">
                    {(findings as any).critical > 0 && <Badge variant="critical" className="text-xs px-1.5">{(findings as any).critical}</Badge>}
                    {(findings as any).high > 0 && <Badge variant="high" className="text-xs px-1.5">{(findings as any).high}</Badge>}
                    {(findings as any).medium > 0 && <Badge variant="medium" className="text-xs px-1.5">{(findings as any).medium}</Badge>}
                    {(findings as any).low > 0 && <Badge variant="low" className="text-xs px-1.5">{(findings as any).low}</Badge>}
                  </div>
                )}
              </div>
            </div>
          );
        })
        )}
      </CardContent>
    </Card>
  );
}

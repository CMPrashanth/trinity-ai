import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Brain, Eye, Hand, Zap, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { agentAPI } from "@/lib/api";

const iconMap: Record<string, React.ElementType> = {
  llm: Brain,
  neo4j: Eye,
  executor: Hand,
  rag: Zap,
};

const statusConfig: Record<string, { icon: React.ElementType; color: string; bgColor: string; label: string; animate?: boolean }> = {
  online: { icon: CheckCircle2, color: "text-primary", bgColor: "bg-primary/10", label: "Online" },
  processing: { icon: Loader2, color: "text-accent", bgColor: "bg-accent/10", label: "Processing", animate: true },
  warning: { icon: AlertCircle, color: "text-warning", bgColor: "bg-warning/10", label: "Warning" },
  offline: { icon: AlertCircle, color: "text-destructive", bgColor: "bg-destructive/10", label: "Offline" },
  degraded: { icon: AlertCircle, color: "text-warning", bgColor: "bg-warning/10", label: "Degraded" },
};

export function AgentStatus() {
  const { data: agentStatus, isLoading } = useQuery({
    queryKey: ["agentStatus"],
    queryFn: agentAPI.getStatus,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  if (isLoading) {
    return (
      <Card variant="terminal">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading Agent Status...
          </CardTitle>
        </CardHeader>
      </Card>
    );
  }

  const overallStatus = agentStatus?.status || "offline";
  const isOnline = overallStatus === "online";

  return (
    <Card variant="terminal">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-lg">
          <div className="relative">
            <div className={cn(
              "h-3 w-3 rounded-full",
              isOnline ? "bg-primary animate-pulse" : "bg-destructive"
            )}></div>
            {isOnline && (
              <div className="absolute inset-0 h-3 w-3 rounded-full bg-primary animate-ping opacity-50"></div>
            )}
          </div>
          Trinity Agent Status
          <Badge 
            variant={isOnline ? "success" : overallStatus === "degraded" ? "warning" : "critical"} 
            className="ml-auto text-xs"
          >
            {overallStatus.toUpperCase()}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {agentStatus?.components.map((component) => {
          const Icon = iconMap[component.id] || Brain;
          const status = statusConfig[component.status] || statusConfig.offline;
          const StatusIcon = status.icon;
          
          // Extract metrics from component details
          let metric;
          if (component.id === "neo4j" && component.details.nodes !== undefined) {
            metric = { label: "Nodes", value: component.details.nodes, max: 10000 };
          } else if (component.id === "executor" && component.details.successRate !== undefined) {
            metric = { label: "Success Rate", value: Math.round(component.details.successRate), max: 100 };
          } else if (component.id === "rag" && component.details.cveCount !== undefined) {
            metric = { label: "CVEs", value: component.details.cveCount, max: 5000 };
          } else if (component.id === "llm" && agentStatus.activity) {
            metric = { label: "Queue", value: agentStatus.activity.queuedScans, max: 10 };
          }

          return (
            <div key={component.id} className="p-4 rounded-lg border border-border bg-card/50 hover:bg-muted/30 transition-colors">
              <div className="flex items-start gap-3">
                <div className={cn("p-2 rounded-lg", status.bgColor)}>
                  <Icon className={cn("h-5 w-5", status.color)} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="font-medium text-sm">{component.name}</h4>
                    <Badge 
                      variant={
                        component.status === "online" ? "success" : 
                        component.status === "processing" ? "info" : 
                        component.status === "warning" ? "warning" :
                        "critical"
                      } 
                      className="text-xs"
                    >
                      <StatusIcon className={cn("h-3 w-3 mr-1", status.animate && "animate-spin")} />
                      {status.label}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{component.description}</p>
                  {metric && (
                    <div className="mt-3">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-muted-foreground">{metric.label}</span>
                        <span className="font-mono text-primary">
                          {metric.value.toLocaleString()}{metric.max === 100 ? '%' : `/${metric.max.toLocaleString()}`}
                        </span>
                      </div>
                      <Progress value={(metric.value / metric.max) * 100} className="h-1.5" />
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

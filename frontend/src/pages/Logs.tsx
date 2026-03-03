import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Layout } from "@/components/layout/Layout";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileText, Search, Download, Activity, AlertTriangle, CheckCircle2, XCircle, RefreshCw, Clock, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { logsAPI } from "@/lib/api";
import { format } from "date-fns";
import { useDebounce } from "@/hooks/use-debounce";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/components/ui/pagination";

const levelConfig: Record<string, { icon: React.ElementType; color: string; bgColor: string }> = {
  info: { icon: Activity, color: "text-accent", bgColor: "bg-accent/10" },
  success: { icon: CheckCircle2, color: "text-primary", bgColor: "bg-primary/10" },
  warning: { icon: AlertTriangle, color: "text-warning", bgColor: "bg-warning/10" },
  error: { icon: XCircle, color: "text-destructive", bgColor: "bg-destructive/10" },
};

const logComponents = ["Planner", "Guard", "Executor", "Observer", "Self-Heal", "RAG", "Circuit Breaker", "Main"];

export default function LogsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebounce(searchQuery, 300);
  const [levelFilter, setLevelFilter] = useState<string>("all");
  const [componentFilter, setComponentFilter] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 15;

  const { data, isLoading, isRefetching, refetch } = useQuery({
    queryKey: ["logs", currentPage, debouncedSearch, levelFilter, componentFilter],
    queryFn: () => logsAPI.list({
      skip: (currentPage - 1) * itemsPerPage,
      limit: itemsPerPage,
      search: debouncedSearch,
      level: levelFilter !== "all" ? levelFilter : undefined,
      component: componentFilter !== "all" ? componentFilter : undefined,
    }),
    placeholderData: (previousData) => previousData,
  });

  const logs = data?.logs || [];
  const totalCount = data?.total || 0;
  const totalPages = Math.ceil(totalCount / itemsPerPage);

  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page);
    }
  };

  return (
    <Layout>
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-muted border border-border">
              <FileText className="h-6 w-6 text-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Activity Logs</h1>
              <p className="text-muted-foreground text-sm">
                {totalCount > 0 ? `Displaying ${logs.length} of ${totalCount} log entries` : "No logs available."}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isRefetching}>
              {isRefetching ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
              Refresh
            </Button>
            <Button variant="default" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Export Logs
            </Button>
          </div>
        </div>

        <Tabs defaultValue="timeline" className="space-y-6">
          <TabsList>
            <TabsTrigger value="timeline">Timeline View</TabsTrigger>
            <TabsTrigger value="terminal">Terminal View</TabsTrigger>
          </TabsList>

          {/* Filters */}
          <Card variant="glow">
            <CardContent className="pt-6">
              <div className="flex flex-col lg:flex-row gap-4">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search logs..."
                    value={searchQuery}
                    onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                    className="pl-10"
                    aria-label="Search logs"
                  />
                </div>
                <Select value={levelFilter} onValueChange={(value) => { setLevelFilter(value); setCurrentPage(1); }}>
                  <SelectTrigger className="w-full lg:w-[150px]" aria-label="Filter by level">
                    <SelectValue placeholder="Level" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Levels</SelectItem>
                    <SelectItem value="info">Info</SelectItem>
                    <SelectItem value="success">Success</SelectItem>
                    <SelectItem value="warning">Warning</SelectItem>
                    <SelectItem value="error">Error</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={componentFilter} onValueChange={(value) => { setComponentFilter(value); setCurrentPage(1); }}>
                  <SelectTrigger className="w-full lg:w-[180px]" aria-label="Filter by component">
                    <SelectValue placeholder="Component" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Components</SelectItem>
                    {logComponents.map(comp => (
                      <SelectItem key={comp} value={comp}>{comp}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Timeline View */}
          <TabsContent value="timeline">
            <Card variant="terminal">
              <CardContent className="p-6">
                {isLoading && <div className="flex justify-center items-center h-64"><Loader2 className="h-8 w-8 animate-spin" /></div>}
                {!isLoading && logs.length === 0 && <div className="text-center text-muted-foreground py-16">No logs found for the current filters.</div>}
                <div className="space-y-4">
                  {logs.map((log, index) => {
                    const config = levelConfig[log.level] || levelConfig.info;
                    const Icon = config.icon;
                    return (
                      <div
                        key={log.id}
                        className={cn(
                          "flex gap-4 p-4 rounded-lg border transition-all hover:bg-muted/30 animate-fade-up",
                          config.bgColor,
                          log.level === "error" ? "border-destructive/30" : "border-border"
                        )}
                        style={{ animationDelay: `${index * 30}ms` }}
                      >
                        <div className={cn("p-2 rounded-lg h-fit", config.bgColor)}>
                          <Icon className={cn("h-4 w-4", config.color)} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-4 mb-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <Badge variant="terminal" className="text-xs">{log.component}</Badge>
                              <span className="font-medium">{log.message}</span>
                            </div>
                            <div className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
                              <Clock className="h-3 w-3" />
                              {format(new Date(log.timestamp), "MMM d, yyyy HH:mm:ss")}
                            </div>
                          </div>
                          {log.details && (
                            <p className="text-sm text-muted-foreground">{log.details}</p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Terminal View */}
          <TabsContent value="terminal">
            <Card variant="terminal">
              <CardHeader className="pb-2 border-b border-border">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-destructive" />
                    <div className="w-3 h-3 rounded-full bg-warning" />
                    <div className="w-3 h-3 rounded-full bg-primary" />
                  </div>
                  <span className="text-xs font-mono text-muted-foreground">trinity-agent-logs</span>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="font-mono text-sm p-4 max-h-[600px] overflow-y-auto space-y-1">
                  {isLoading && <div className="flex justify-center items-center h-64"><Loader2 className="h-8 w-8 animate-spin" /></div>}
                  {!isLoading && logs.length === 0 && <div className="text-center text-muted-foreground py-16">No logs found.</div>}
                  {logs.map((log) => (
                    <div key={log.id} className="flex gap-2">
                      <span className="text-muted-foreground shrink-0">[{format(new Date(log.timestamp), "HH:mm:ss")}]</span>
                      <span className={cn(
                        "shrink-0",
                        log.level === "info" && "text-accent",
                        log.level === "success" && "text-primary",
                        log.level === "warning" && "text-warning",
                        log.level === "error" && "text-destructive"
                      )}>
                        [{log.level.toUpperCase()}]
                      </span>
                      <span className="text-muted-foreground">({log.component})</span>
                      <span>{log.message}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Pagination */}
        {totalPages > 1 && (
          <Pagination className="mt-6">
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious onClick={() => handlePageChange(currentPage - 1)} aria-disabled={currentPage === 1} />
              </PaginationItem>
              {[...Array(totalPages)].map((_, i) => (
                <PaginationItem key={i}>
                  <PaginationLink onClick={() => handlePageChange(i + 1)} isActive={currentPage === i + 1}>
                    {i + 1}
                  </PaginationLink>
                </PaginationItem>
              ))}
              <PaginationItem>
                <PaginationNext onClick={() => handlePageChange(currentPage + 1)} aria-disabled={currentPage === totalPages} />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        )}
      </div>
    </Layout>
  );
}

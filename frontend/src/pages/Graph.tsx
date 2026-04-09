import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import ForceGraph2D, { ForceGraphMethods, NodeObject, LinkObject } from "react-force-graph-2d";
import { Layout } from "@/components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Network, ZoomIn, ZoomOut, LocateFixed, RefreshCw, Download, Loader2 } from "lucide-react";
import { graphAPI, GraphData, scansAPI, Scan } from "@/lib/api";
import { useTheme } from "next-themes";
import { useNavigate, useSearchParams } from "react-router-dom";
import { forceCenter, forceLink, forceManyBody } from 'd3-force';
import "./graph-colors.css";

const nodeColors: Record<string, string> = {
  host: "hsl(185, 100%, 40%)",
  network: "hsl(218, 86%, 64%)",
  port: "hsl(142, 71%, 45%)",
  vulnerability: "hsl(0, 85%, 55%)",
  cve: "hsl(34, 97%, 55%)",
  service: "hsl(262, 85%, 60%)",
};

// Map backend types (possibly inconsistent case or variations) to our canonical legend keys
const normalizeNodeType = (type: string | undefined): string => {
  const t = (type || "").toLowerCase().trim();
  if (t === "host" || t === "computer" || t === "device") return "host";
  if (t === "network" || t === "subnet") return "network";
  if (t === "port" || t === "open_port") return "port";
  if (t === "vulnerability" || t === "vuln" || t === "issue") return "vulnerability";
  if (t === "cve" || t === "advisory") return "cve";
  if (t === "service" || t === "app") return "service";
  return "host"; // Default fallback
};


const legendDotClass: Record<string, string> = {
  host: "graph-legend-dot-host",
  network: "graph-legend-dot-network",
  port: "graph-legend-dot-port",
  vulnerability: "graph-legend-dot-vulnerability",
  cve: "graph-legend-dot-cve",
  service: "graph-legend-dot-service",
};

const severityClass: Record<string, string> = {
  critical: "graph-sev-critical",
  high: "graph-sev-high",
  medium: "graph-sev-medium",
  low: "graph-sev-low",
  info: "graph-sev-info",
};

const nodeLegend: Array<{ type: string; label: string }> = [
  { type: "host", label: "Host" },
  { type: "network", label: "Network" },
  { type: "port", label: "Port" },
  { type: "vulnerability", label: "Vulnerability" },
  { type: "cve", label: "CVE" },
  { type: "service", label: "Service" },
];

const shorten = (value: string, max: number) => {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
};

const getReadableNodeLabel = (node: any): string => {
  const type = String(node?.type ?? "").toLowerCase();
  const props = node?.properties ?? {};
  const rawLabel = String(node?.label ?? "").trim();

  if (type === "vulnerability") {
    const title = String(props?.title ?? "").trim();
    const cve = String(props?.cve_id ?? props?.cve ?? "").trim();
    const vulnId = String(props?.vuln_id ?? "").trim();

    if (title && cve && !title.toUpperCase().includes(cve.toUpperCase())) {
      return `${title} (${cve})`;
    }
    if (title) return title;
    if (cve) return cve;
    if (vulnId) return vulnId;
    return rawLabel || "Unknown vulnerability";
  }

  if (type === "cve") {
    const value = props?.cve_id ?? rawLabel;
    return String(value || "Unknown CVE").trim();
  }

  if (type === "host") {
    const value = props?.ip ?? rawLabel;
    return String(value || "Unknown host").trim();
  }

  if (type === "network") {
    const value = props?.cidr ?? rawLabel;
    return String(value || "Unknown network").trim();
  }

  if (type === "port") {
    const number = props?.number;
    const service = String(props?.service ?? "").trim();
    if (number != null && service) return `${number}/${service}`;
    if (number != null) return String(number);
    return rawLabel || "Unknown port";
  }

  if (type === "service") {
    const value = props?.name ?? rawLabel;
    return String(value || "Unknown service").trim();
  }

  return rawLabel || "Unknown";
};

export default function GraphPage() {
  const { theme, resolvedTheme } = useTheme();
  const isDark = (resolvedTheme ?? theme) === 'dark';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const scanId = useMemo(() => {
    return searchParams.get("scan_id") ?? searchParams.get("scanId");
  }, [searchParams]);
  const fgRef = useRef<ForceGraphMethods>();
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState<NodeObject | null>(null);
  const [hasAutoFit, setHasAutoFit] = useState(false);

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ["graphData", scanId ?? "global"],
    queryFn: () => graphAPI.get(scanId),
  });

  const {
    data: recentScanData,
    isLoading: isRecentScansLoading,
  } = useQuery({
    queryKey: ["recentCompletedScans"],
    queryFn: () => scansAPI.list({ limit: 8, status: "completed" }),
  });

  const recentCompletedScans = recentScanData?.scans ?? [];

  useEffect(() => {
    if (!scanId && recentCompletedScans.length > 0) {
      navigate(`/graph?scan_id=${encodeURIComponent(recentCompletedScans[0].scan_id)}`, { replace: true });
    }
  }, [scanId, recentCompletedScans, navigate]);

  useEffect(() => {
    setHasAutoFit(false);
  }, [scanId]);

  useEffect(() => {
    if (data) {
      const processedNodes = data.nodes.map(node => ({
        ...node,
        id: node.id,
        name: getReadableNodeLabel(node),
      }));
      setGraphData({ nodes: processedNodes, links: data.links });
    }
  }, [data]);

  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
      // Safely access existing forces initialized by react-force-graph
      const linkForce = fgRef.current.d3Force('link');
      if (linkForce) linkForce.distance(80);
      
      const chargeForce = fgRef.current.d3Force('charge');
      if (chargeForce) chargeForce.strength(-180);

      // On first render, the ref may not be ready when data arrives.
      // Schedule a fit on the next tick to avoid requiring manual "fit view" clicks.
      if (!hasAutoFit) {
        setTimeout(() => {
          fgRef.current?.zoomToFit(600, 100);
          setHasAutoFit(true);
        }, 0);
      }
    }
  }, [graphData, hasAutoFit]);

  const handleNodeClick = useCallback((node: NodeObject) => {
    setSelectedNode(node);
    fgRef.current?.centerAt(node.x, node.y, 1000);
    fgRef.current?.zoom(1.5, 1000);
  }, []);

  const handleZoom = (direction: 'in' | 'out') => {
    const currentZoom = fgRef.current?.zoom() || 1;
    fgRef.current?.zoom(direction === 'in' ? currentZoom * 1.2 : currentZoom / 1.2, 500);
  };

  const handleFitView = () => {
    fgRef.current?.zoomToFit(500, 100);
  };

  const handleSelectScan = useCallback((selectedScan: Scan) => {
    navigate(`/graph?scan_id=${encodeURIComponent(selectedScan.scan_id)}`);
  }, [navigate]);

  const selectedScanSummary = useMemo(() => {
    if (!scanId) return null;
    return recentCompletedScans.find((scan) => scan.scan_id === scanId) ?? null;
  }, [recentCompletedScans, scanId]);

  const renderNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = String(node.name ?? "");
    const canvasLabel = shorten(label, 34);
    const fontSize = 12 / globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;

    const baseRadius = node.type === 'host' ? 12 : 8;
    const radius = baseRadius / Math.sqrt(globalScale);

    // Normalize type for color lookup (backend might send capitalized Types)
    // Use the robust normalization helper to ensure Legend consistency
    const normalizedType = normalizeNodeType(String(node.type));
    const color = nodeColors[normalizedType] || 'grey';

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = color;
    ctx.fill();

    if (selectedNode && node.id === selectedNode.id) {
      ctx.strokeStyle = isDark ? 'white' : 'black';
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }

    const textY = node.y + radius + 12 / globalScale;
    const labelPaddingX = 4 / globalScale;
    const labelPaddingY = 2 / globalScale;
    const labelWidth = ctx.measureText(canvasLabel).width;
    const bgX = node.x - (labelWidth / 2) - labelPaddingX;
    const bgY = textY - fontSize / 2 - labelPaddingY;
    const bgW = labelWidth + labelPaddingX * 2;
    const bgH = fontSize + labelPaddingY * 2;

    // Draw a subtle backdrop so labels stay readable even over graph edges.
    ctx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.88)' : 'rgba(255, 255, 255, 0.9)';
    ctx.fillRect(bgX, bgY, bgW, bgH);

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = isDark ? 'white' : 'black';
    ctx.fillText(canvasLabel, node.x, textY);
  }, [selectedNode, isDark]);

  return (
    <Layout>
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-accent/10 border border-accent/30">
              <Network className="h-6 w-6 text-accent" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Attack Graph</h1>
              <p className="text-muted-foreground text-sm">Neo4j-powered attack path visualization</p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <div className="w-[200px]">
              <Select 
                value={scanId || ""} 
                onValueChange={(val) => navigate(`/graph?scan_id=${encodeURIComponent(val)}`)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a scan..." />
                </SelectTrigger>
                <SelectContent>
                  {recentCompletedScans.map((scan) => (
                    <SelectItem key={scan.scan_id} value={scan.scan_id}>
                      {scan.target} ({scan.profile})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button variant="outline" size="sm" onClick={() => handleZoom('out')}><ZoomOut className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" onClick={() => handleZoom('in')}><ZoomIn className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" onClick={handleFitView}><LocateFixed className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isRefetching}>
              {isRefetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            </Button>
            <Button variant="default" size="sm"><Download className="h-4 w-4 mr-2" />Export</Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Graph Canvas */}
          <Card variant="terminal" className="lg:col-span-3">
            <CardContent className="p-0 relative">
              {isLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
                  <Loader2 className="h-10 w-10 animate-spin" />
                </div>
              )}
              <ForceGraph2D
                ref={fgRef}
                graphData={graphData}
                nodeCanvasObject={renderNode}
                linkWidth={2}
                // High contrast white for dark mode (opacity 0.9), dark grey for light mode
                linkColor={() => isDark ? 'rgba(255, 255, 255, 0.9)' : 'rgba(50, 50, 50, 0.8)'}
                linkDirectionalParticles={2}
                linkDirectionalParticleWidth={2}
                linkDirectionalParticleColor={() => isDark ? '#00e5ff' : '#0070f3'}
                onNodeClick={handleNodeClick}
                onBackgroundClick={() => setSelectedNode(null)}
                onEngineStop={() => {
                  // Another safety net to ensure nodes are in view after refresh.
                  fgRef.current?.zoomToFit(600, 100);
                }}
                width={800}
                height={600}
                cooldownTicks={100}
              />
              {/* Legend */}
              <div className="absolute bottom-4 left-4 p-3 rounded-lg bg-card/90 border border-border backdrop-blur-sm">
                <p className="text-xs font-medium mb-2">Legend</p>
                <div className="space-y-1.5">
                  {nodeLegend.map(({ type, label }) => (
                    <div key={type} className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${legendDotClass[type] ?? ''}`} />
                      <span className="text-xs text-muted-foreground">{label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Node Details Sidebar */}
          <div className="space-y-4">
            <Card variant="glow">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Recent Completed Scans</CardTitle>
                <CardDescription>Click any scan to load its attack graph</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {isRecentScansLoading ? (
                    <div className="flex items-center justify-center py-8 text-muted-foreground">
                      <Loader2 className="h-5 w-5 animate-spin" />
                    </div>
                  ) : recentCompletedScans.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No completed scans yet.</p>
                  ) : (
                    recentCompletedScans.map((scan) => {
                      const isActive = scan.scan_id === scanId;
                      return (
                        <button
                          key={scan.scan_id}
                          type="button"
                          onClick={() => handleSelectScan(scan)}
                          className={`w-full text-left p-2 rounded-md border transition-colors ${
                            isActive
                              ? "border-primary bg-primary/10"
                              : "border-border hover:border-primary/50 hover:bg-muted/60"
                          }`}
                        >
                          <p className="text-sm font-medium break-all">{scan.scan_id}</p>
                          <p className="text-xs text-muted-foreground truncate">{scan.target}</p>
                          <div className="mt-1 flex items-center gap-2">
                            <Badge variant="outline" className="text-[10px]">{scan.profile}</Badge>
                            <Badge variant="outline" className="text-[10px]">{scan.findings?.critical ?? 0} critical</Badge>
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              </CardContent>
            </Card>

            <Card variant="glow">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Node Details</CardTitle>
                <CardDescription>Select a node to see its properties</CardDescription>
              </CardHeader>
              <CardContent>
                {selectedScanSummary && (
                  <div className="mb-4 rounded-md border border-border bg-muted/40 p-2">
                    <p className="text-xs text-muted-foreground mb-1">Viewing Scan</p>
                    <p className="text-xs font-medium break-all">{selectedScanSummary.scan_id}</p>
                    <p className="text-xs text-muted-foreground truncate">{selectedScanSummary.target}</p>
                  </div>
                )}
                {selectedNode ? (
                  <div className="space-y-4 animate-fade-in">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Type</p>
                      <Badge variant="terminal" style={{ borderColor: nodeColors[(selectedNode as any).type] }}>
                        {(selectedNode as any).type.toUpperCase()}
                      </Badge>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Identifier</p>
                      <p className="font-mono text-primary break-all">{(selectedNode as any).name}</p>
                    </div>
                    {Object.entries((selectedNode as any).properties || {}).map(([key, value]) => (
                      <div key={key}>
                        <p className="text-xs text-muted-foreground mb-1 capitalize">{key.replace(/_/g, ' ')}</p>
                        {key === 'severity' ? (
                           <Badge className={severityClass[String(value).toLowerCase()] ?? undefined}>
                             {String(value)}
                           </Badge>
                        ) : (
                          <p className="text-sm break-all">{String(value)}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center text-muted-foreground py-10">
                    <Network className="mx-auto h-10 w-10 mb-2" />
                    <p>No node selected</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </Layout>
  );
}

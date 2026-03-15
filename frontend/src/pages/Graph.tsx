import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import ForceGraph2D, { ForceGraphMethods, NodeObject, LinkObject } from "react-force-graph-2d";
import { Layout } from "@/components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Network, ZoomIn, ZoomOut, LocateFixed, RefreshCw, Download, Loader2 } from "lucide-react";
import { graphAPI, GraphData } from "@/lib/api";
import { useTheme } from "next-themes";
import { forceCenter, forceLink, forceManyBody } from 'd3-force';
import "./graph-colors.css";

const nodeColors: Record<string, string> = {
  host: "hsl(185, 100%, 40%)",
  port: "hsl(142, 71%, 45%)",
  vulnerability: "hsl(0, 85%, 55%)",
  cve: "hsl(34, 97%, 55%)",
  service: "hsl(262, 85%, 60%)",
};

const severityColors: Record<string, string> = {
  critical: "hsl(0, 85%, 55%)",
  high: "hsl(34, 97%, 55%)",
  medium: "hsl(48, 95%, 55%)",
  low: "hsl(142, 71%, 45%)",
  info: "hsl(210, 40%, 82%)",
};

const legendDotClass: Record<string, string> = {
  host: "graph-legend-dot-host",
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

export default function GraphPage() {
  const { theme, resolvedTheme } = useTheme();
  const isDark = (resolvedTheme ?? theme) === 'dark';
  const fgRef = useRef<ForceGraphMethods>();
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState<NodeObject | null>(null);
  const [hasAutoFit, setHasAutoFit] = useState(false);

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ["graphData"],
    queryFn: graphAPI.get,
  });

  useEffect(() => {
    if (data) {
      const processedNodes = data.nodes.map(node => ({
        ...node,
        id: node.id,
        name: node.label,
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

  const renderNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.name;
    const fontSize = 12 / globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;

    const baseRadius = node.type === 'host' ? 12 : 8;
    const radius = baseRadius / Math.sqrt(globalScale);

    const color = node.properties?.severity 
      ? severityColors[node.properties.severity.toLowerCase()] || nodeColors.vulnerability
      : nodeColors[node.type] || 'grey';

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = color;
    ctx.fill();

    if (selectedNode && node.id === selectedNode.id) {
      ctx.strokeStyle = isDark ? 'white' : 'black';
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    // Improve readability against both light/dark backgrounds.
    ctx.lineWidth = 3 / globalScale;
    ctx.strokeStyle = isDark ? 'rgba(0, 0, 0, 0.85)' : 'rgba(255, 255, 255, 0.9)';
    ctx.strokeText(label, node.x, node.y + radius + 5);
    ctx.fillStyle = isDark ? 'white' : 'black';
    ctx.fillText(label, node.x, node.y + radius + 5);
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
                linkWidth={1.5}
                // Use resolved theme, not the raw "theme" setting (can be "system").
                linkColor={() => isDark ? 'rgba(255, 255, 255, 0.55)' : 'rgba(0, 0, 0, 0.35)'}
                linkDirectionalParticles={2}
                linkDirectionalParticleWidth={2}
                linkDirectionalParticleColor={() => "hsl(var(--primary))"}
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
                  {Object.entries(nodeColors).map(([type, color]) => (
                    <div key={type} className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${legendDotClass[type] ?? ''}`} />
                      <span className="text-xs text-muted-foreground capitalize">{type}</span>
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
                <CardTitle className="text-lg">Node Details</CardTitle>
                <CardDescription>Select a node to see its properties</CardDescription>
              </CardHeader>
              <CardContent>
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

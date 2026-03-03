import { Layout } from "@/components/layout/Layout";
import { MetricsPanel } from "@/components/dashboard/MetricsPanel";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { VulnerabilityChart } from "@/components/dashboard/VulnerabilityChart";
import { AgentStatus } from "@/components/dashboard/AgentStatus";
import { RecentScans } from "@/components/dashboard/RecentScans";
import { Button } from "@/components/ui/button";
import { Target, Zap } from "lucide-react";
import { Link } from "react-router-dom";

const Index = () => {
  return (
    <Layout>
      {/* Hero Section */}
      <section className="relative py-16 lg:py-24 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/5 via-transparent to-transparent" />
        <div className="container mx-auto px-4 relative">
          <div className="max-w-3xl mx-auto text-center mb-12">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-muted border border-primary/30 mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
              </span>
              <span className="text-sm font-mono text-primary">TRINITY AGENT v1.0</span>
            </div>
            <h1 className="text-4xl lg:text-5xl font-bold mb-6 leading-tight">
              Autonomous <span className="text-primary text-glow">Pentesting</span> with
              <br />Neuro-Symbolic Intelligence
            </h1>
            <p className="text-lg text-muted-foreground mb-8 max-w-2xl mx-auto">
              A stateful security agent featuring LLM-driven planning, graph-based attack path memory, 
              and self-healing code execution with circuit breaker protection.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/scan">
                <Button variant="hero" size="xl">
                  <Target className="h-5 w-5" />
                  Start New Scan
                </Button>
              </Link>
              <Link to="/graph">
                <Button variant="outline" size="lg">
                  <Zap className="h-5 w-5" />
                  View Attack Graph
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Metrics */}
      <section className="container mx-auto px-4 pb-8">
        <MetricsPanel />
      </section>

      {/* Main Dashboard Grid */}
      <section className="container mx-auto px-4 pb-16">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <RecentScans />
            <VulnerabilityChart />
          </div>
          <div className="space-y-6">
            <AgentStatus />
            <ActivityFeed />
          </div>
        </div>
      </section>
    </Layout>
  );
};

export default Index;

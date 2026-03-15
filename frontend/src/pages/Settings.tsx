import { useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout/Layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Settings as SettingsIcon, Database, Brain, Shield, Bell, Save, RotateCcw, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { cvesAPI, settingsAPI, Settings } from "@/lib/api";
import { usePersistentState } from "@/hooks/use-persistent-state";

export default function SettingsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: initialSettings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsAPI.get,
  });

  const storageNamespace = useMemo(() => {
    if (typeof window === "undefined") {
      return "";
    }
    try {
      const rawUser = window.localStorage.getItem("user");
      if (rawUser) {
        const parsed = JSON.parse(rawUser);
        if (parsed?.id) {
          return `user:${parsed.id}:`;
        }
      }
    } catch (error) {
      console.warn("Unable to derive storage namespace:", error);
    }
    return "";
  }, []);

  const [settings, setSettings] = usePersistentState<Partial<Settings>>(`${storageNamespace}settings:draft`, {});

  useEffect(() => {
    if (initialSettings) {
      setSettings((prev) => {
        if (prev && Object.keys(prev).length > 0) {
          return prev;
        }
        return { ...initialSettings };
      });
    }
  }, [initialSettings, setSettings]);

  const mutation = useMutation({
    mutationFn: settingsAPI.update,
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], data);
      setSettings({ ...data });
      toast({
        title: "Settings Saved",
        description: "Your configuration has been updated successfully.",
      });
    },
    onError: (error) => {
      toast({
        title: "Save Failed",
        description: `Could not save settings: ${error.message}`,
        variant: "destructive",
      });
    },
  });

  const testN8nMutation = useMutation({
    mutationFn: settingsAPI.testN8n,
    onSuccess: (data) => {
      toast({
        title: "n8n Connected",
        description: data?.message || "Test event sent to n8n.",
      });
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail;
      toast({
        title: "n8n Test Failed",
        description: `Could not send test event: ${detail || error.message}`,
        variant: "destructive",
      });
    },
  });

  const { data: chromaStatus, isFetching: isChromaFetching, refetch: refetchChromaStatus } = useQuery({
    queryKey: ["chroma", "status"],
    queryFn: cvesAPI.status,
  });

  const seedDemoMutation = useMutation({
    mutationFn: (reset: boolean) => cvesAPI.seedDemo(reset),
    onSuccess: (data) => {
      toast({
        title: "CVE Knowledge Base Seeded",
        description: `Added ${data.added} CVEs (total: ${data.count}).`,
      });
      refetchChromaStatus();
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail;
      toast({
        title: "Seed Failed",
        description: detail || error.message || "Could not seed demo CVEs.",
        variant: "destructive",
      });
    },
  });

  const syncCvesMutation = useMutation({
    mutationFn: settingsAPI.syncCvesNow,
    onSuccess: (data) => {
      toast({
        title: "CVE Sync Queued",
        description: data?.taskId ? `Task queued: ${data.taskId}` : (data?.message || "CVE sync task queued."),
      });
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail;
      toast({
        title: "CVE Sync Failed",
        description: detail || error.message || "Could not queue CVE sync task.",
        variant: "destructive",
      });
    },
  });

  const handleSave = () => {
    mutation.mutate(settings as Settings);
  };

  const handleReset = () => {
    if (initialSettings) {
      setSettings({ ...initialSettings });
      toast({
        title: "Settings Reset",
        description: "Configuration restored to last saved values.",
        variant: "default",
      });
    }
  };

  const handleSettingChange = (key: keyof Settings, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-full">
          <Loader2 className="h-16 w-16 animate-spin" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-muted border border-border">
              <SettingsIcon className="h-6 w-6 text-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Settings</h1>
              <p className="text-muted-foreground text-sm">Configure Trinity Agent behavior and integrations</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={handleReset} disabled={mutation.isPending}>
              <RotateCcw className="h-4 w-4 mr-2" />
              Reset
            </Button>
            <Button variant="default" onClick={handleSave} disabled={mutation.isPending}>
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Save Changes
            </Button>
          </div>
        </div>

        <Tabs defaultValue="agent" className="space-y-6">
          <TabsList className="grid w-full grid-cols-2 lg:grid-cols-4">
            <TabsTrigger value="agent" className="gap-2"><Brain className="h-4 w-4" />Agent</TabsTrigger>
            <TabsTrigger value="database" className="gap-2"><Database className="h-4 w-4" />Database</TabsTrigger>
            <TabsTrigger value="security" className="gap-2"><Shield className="h-4 w-4" />Security</TabsTrigger>
            <TabsTrigger value="notifications" className="gap-2"><Bell className="h-4 w-4" />Notifications</TabsTrigger>
          </TabsList>

          {/* Agent Settings */}
          <TabsContent value="agent">
            <div className="grid gap-6">
              <Card variant="glow">
                <CardHeader>
                  <CardTitle>LLM Configuration</CardTitle>
                  <CardDescription>Configure the language model used for planning</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-2">
                    <Label>Model</Label>
                    <Select value={settings.llm_model} onValueChange={(v) => handleSettingChange('llm_model', v)}>
                      <SelectTrigger aria-label="Select LLM model">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="llama3.1:8b-instruct">Llama 3.1 8B Instruct</SelectItem>
                        <SelectItem value="llama3.1:70b-instruct">Llama 3.1 70B Instruct</SelectItem>
                        <SelectItem value="codellama:13b">CodeLlama 13B</SelectItem>
                        <SelectItem value="mistral:7b-instruct">Mistral 7B Instruct</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">Must support JSON mode for structured output</p>
                  </div>

                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <Label>Execution Timeout</Label>
                      <span className="text-sm font-mono text-primary">{settings.execution_timeout}s</span>
                    </div>
                    <Slider
                      value={[settings.execution_timeout || 30]}
                      onValueChange={([v]) => handleSettingChange('execution_timeout', v)}
                      min={10}
                      max={120}
                      step={5}
                      aria-label="Execution timeout slider"
                    />
                  </div>

                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <Label>Max Retries (Circuit Breaker)</Label>
                      <span className="text-sm font-mono text-primary">{settings.max_retries}</span>
                    </div>
                    <Slider
                      value={[settings.max_retries || 3]}
                      onValueChange={([v]) => handleSettingChange('max_retries', v)}
                      min={1}
                      max={5}
                      step={1}
                      aria-label="Max retries slider"
                    />
                  </div>
                </CardContent>
              </Card>

              <Card variant="terminal">
                <CardHeader>
                  <CardTitle>Agent Behavior</CardTitle>
                  <CardDescription>Toggle advanced agent features</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 pt-6">
                  <div className="flex items-center justify-between p-4 rounded-lg border border-border">
                    <div>
                      <Label className="text-base">Self-Healing</Label>
                      <p className="text-xs text-muted-foreground">LLM automatically rewrites failed scripts</p>
                    </div>
                    <Switch
                      checked={settings.enable_self_healing}
                      onCheckedChange={(v) => handleSettingChange('enable_self_healing', v)}
                      aria-label="Toggle self-healing"
                    />
                  </div>

                  <div className="flex items-center justify-between p-4 rounded-lg border border-border">
                    <div>
                      <Label className="text-base">Circuit Breaker</Label>
                      <p className="text-xs text-muted-foreground">Abort tasks after max consecutive failures</p>
                    </div>
                    <Switch
                      checked={settings.circuit_breaker_enabled}
                      onCheckedChange={(v) => handleSettingChange('circuit_breaker_enabled', v)}
                      aria-label="Toggle circuit breaker"
                    />
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Database Settings */}
          <TabsContent value="database">
            <div className="grid gap-6">
              <Card variant="glow">
                <CardHeader>
                  <CardTitle>Neo4j Graph Database</CardTitle>
                  <CardDescription>Attack path memory storage configuration</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 pt-6">
                  <div className="space-y-2">
                    <Label>Connection URI</Label>
                    <Input
                      value={settings.neo4j_uri}
                      onChange={(e) => handleSettingChange('neo4j_uri', e.target.value)}
                      className="font-mono"
                      aria-label="Neo4j connection URI"
                    />
                  </div>
                  <div className="flex items-center justify-between pt-2">
                    <Label>Automatic Graph Hygiene</Label>
                    <Switch
                      checked={settings.graph_hygiene_enabled}
                      onCheckedChange={(v) => handleSettingChange('graph_hygiene_enabled', v)}
                      aria-label="Toggle graph hygiene"
                    />
                  </div>
                </CardContent>
              </Card>
              <Card variant="terminal">
                <CardHeader>
                  <CardTitle>Chroma Vector Database</CardTitle>
                  <CardDescription>Configuration for RAG and vulnerability lookups</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 pt-6">
                  <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 p-4 rounded-lg border border-border bg-muted/30">
                    <div>
                      <Label className="text-base">CVE Knowledge Base</Label>
                      <p className="text-xs text-muted-foreground">
                        Status: {chromaStatus?.status || (isChromaFetching ? "checking..." : "unknown")}
                        {typeof chromaStatus?.count === "number" ? ` • Records: ${chromaStatus.count}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        onClick={() => seedDemoMutation.mutate(false)}
                        disabled={seedDemoMutation.isPending}
                      >
                        {seedDemoMutation.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                        Seed Demo CVEs
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => syncCvesMutation.mutate()}
                        disabled={syncCvesMutation.isPending}
                      >
                        {syncCvesMutation.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                        Sync CVEs Now
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => refetchChromaStatus()}
                        disabled={isChromaFetching}
                      >
                        {isChromaFetching ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                        Refresh
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Database Path</Label>
                    <Input
                      value={settings.chroma_db_path}
                      onChange={(e) => handleSettingChange('chroma_db_path', e.target.value)}
                      className="font-mono"
                      aria-label="ChromaDB path"
                    />
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Security Settings */}
          <TabsContent value="security">
            <Card variant="glow">
              <CardHeader>
                <CardTitle>Execution Scope & Rules</CardTitle>
                <CardDescription>Define the agent's operational boundaries</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6 pt-6">
                <div className="space-y-2">
                  <Label>Allowed Subnet (CIDR)</Label>
                  <Input
                    value={settings.allowed_subnet}
                    onChange={(e) => handleSettingChange('allowed_subnet', e.target.value)}
                    className="font-mono"
                    placeholder="e.g., 192.168.1.0/24"
                    aria-label="Allowed subnet"
                  />
                  <p className="text-xs text-muted-foreground">The agent will only interact with IPs in this range.</p>
                </div>
                <div className="space-y-2">
                  <Label>Blocked Commands</Label>
                  <Input
                    value={settings.blocked_commands}
                    onChange={(e) => handleSettingChange('blocked_commands', e.target.value)}
                    className="font-mono"
                    placeholder="e.g., rm -rf, fdisk"
                    aria-label="Blocked commands"
                  />
                  <p className="text-xs text-muted-foreground">Comma-separated list of forbidden commands or flags.</p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Notifications Settings */}
          <TabsContent value="notifications">
            <Card variant="glow">
              <CardHeader>
                <CardTitle>Alerting & Notifications</CardTitle>
                <CardDescription>Configure how and when you receive alerts</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 pt-6">
                <div className="flex items-center justify-between p-4 rounded-lg border border-border">
                  <div>
                    <Label className="text-base">n8n Webhook</Label>
                    <p className="text-xs text-muted-foreground">Send a test event to verify workflow connection</p>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => testN8nMutation.mutate()}
                    disabled={testN8nMutation.isPending}
                  >
                    {testN8nMutation.isPending ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : null}
                    Test Connection
                  </Button>
                </div>
                <div className="flex items-center justify-between p-4 rounded-lg border border-border">
                  <div>
                    <Label className="text-base">Email Alerts</Label>
                    <p className="text-xs text-muted-foreground">Send alerts to the administrator's email</p>
                  </div>
                  <Switch
                    checked={settings.email_alerts}
                    onCheckedChange={(v) => handleSettingChange('email_alerts', v)}
                    aria-label="Toggle email alerts"
                  />
                </div>
                <div className="flex items-center justify-between p-4 rounded-lg border border-border">
                  <div>
                    <Label className="text-base">Slack Integration</Label>
                    <p className="text-xs text-muted-foreground">Post alerts to a configured Slack channel</p>
                  </div>
                  <Switch
                    checked={settings.slack_integration}
                    onCheckedChange={(v) => handleSettingChange('slack_integration', v)}
                    aria-label="Toggle Slack integration"
                    disabled
                  />
                </div>
                <div className="flex items-center justify-between p-4 rounded-lg border border-border">
                  <div>
                    <Label className="text-base">Alert on Critical Vulnerability</Label>
                    <p className="text-xs text-muted-foreground">Notify when a critical vulnerability is found</p>
                  </div>
                  <Switch
                    checked={settings.alert_on_critical}
                    onCheckedChange={(v) => handleSettingChange('alert_on_critical', v)}
                    aria-label="Toggle critical vulnerability alerts"
                  />
                </div>
                <div className="flex items-center justify-between p-4 rounded-lg border border-border">
                  <div>
                    <Label className="text-base">Alert on Circuit Breaker Trip</Label>
                    <p className="text-xs text-muted-foreground">Notify when a task is aborted by the circuit breaker</p>
                  </div>
                  <Switch
                    checked={settings.alert_on_circuit_break}
                    onCheckedChange={(v) => handleSettingChange('alert_on_circuit_break', v)}
                    aria-label="Toggle circuit breaker alerts"
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
}

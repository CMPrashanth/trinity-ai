import { useMemo } from "react";
import { Layout } from "@/components/layout/Layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Target, Play, Settings, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { scansAPI, ScanCreate } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { usePersistentState } from "@/hooks/use-persistent-state";

const scanProfiles = [
	{ id: "quick", name: "Quick Scan", description: "Fast port scan with basic service detection", duration: "~5 min" },
	{ id: "full", name: "Full Assessment", description: "Comprehensive vulnerability assessment", duration: "~30 min" },
	{ id: "stealth", name: "Stealth Mode", description: "Low-profile scanning to avoid detection", duration: "~45 min" },
	{ id: "web", name: "Web Application", description: "OWASP-focused web vulnerability scan", duration: "~20 min" },
];

export default function ScanPage() {
	const { toast } = useToast();
	const navigate = useNavigate();
	const queryClient = useQueryClient();

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

	const [target, setTarget] = usePersistentState(`${storageNamespace}scan:target`, "");
	const [scanProfile, setScanProfile] = usePersistentState(`${storageNamespace}scan:profile`, "quick");
	const [advancedOptions, setAdvancedOptions] = usePersistentState(`${storageNamespace}scan:advanced`, {
		enableRAG: true,
		circuitBreaker: true,
		graphMemory: true,
		autoHeal: true,
	});

	const createScanMutation = useMutation({
		mutationFn: (data: ScanCreate) => scansAPI.create(data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["scans", "recent"] });
			toast({
				title: "Scan Initiated",
				description: `Starting ${scanProfiles.find((p) => p.id === scanProfile)?.name} on ${target}`,
			});
			setTarget("");
			setScanProfile("quick");
			setAdvancedOptions({
				enableRAG: true,
				circuitBreaker: true,
				graphMemory: true,
				autoHeal: true,
			});
			navigate("/");
		},
		onError: (error: any) => {
			toast({
				title: "Scan Failed",
				description: error.response?.data?.detail || "Failed to start scan. Please try again.",
				variant: "destructive",
			});
		},
	});

	const handleStartScan = () => {
		if (!target.trim()) {
			toast({ title: "Target Required", description: "Please enter a valid target IP or subnet.", variant: "destructive" });
			return;
		}

		const scanData: ScanCreate = {
			target: target.trim(),
			scan_profile: scanProfile as ScanCreate["scan_profile"],
			advancedOptions: advancedOptions,
		};
		createScanMutation.mutate(scanData);
	};

	return (
		<Layout>
			<div className="container mx-auto px-4 py-8">
				{/* Page Header */}
				<div className="mb-8">
					<div className="flex items-center gap-3 mb-2">
						<div className="p-2 rounded-lg bg-primary/10 border border-primary/30">
							<Target className="h-6 w-6 text-primary" />
						</div>
						<div>
							<h1 className="text-2xl font-bold">New Scan</h1>
							<p className="text-muted-foreground text-sm">Configure and launch a new penetration test</p>
						</div>
					</div>
				</div>

				<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
					{/* Main Configuration */}
					<div className="lg:col-span-2 space-y-6">
						<Card variant="glow">
							<CardHeader>
								<CardTitle className="text-lg">Target Configuration</CardTitle>
								<CardDescription>Define the scope for this assessment</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6 pt-6">
								<div className="space-y-2">
									<Label htmlFor="target">Target IP / Subnet</Label>
									<Input
										id="target"
										placeholder="e.g., 192.168.1.0/24 or 10.0.0.15"
										value={target}
										onChange={(e) => setTarget(e.target.value)}
										className="font-mono"
										aria-label="Target IP address or subnet"
										disabled={createScanMutation.isPending}
									/>
									<p className="text-xs text-muted-foreground">
										Supports CIDR notation. The agent will only operate within this defined scope.
									</p>
								</div>

								<div className="space-y-2">
									<Label>Scan Profile</Label>
									<Tabs value={scanProfile} onValueChange={setScanProfile}>
										<TabsList className="grid grid-cols-2 lg:grid-cols-4 h-auto">
											{scanProfiles.map((profile) => (
												<TabsTrigger key={profile.id} value={profile.id} className="py-3" disabled={createScanMutation.isPending}>
													{profile.name}
												</TabsTrigger>
											))}
										</TabsList>
										{scanProfiles.map((profile) => (
											<TabsContent key={profile.id} value={profile.id} className="mt-4">
												<div className="p-4 rounded-lg bg-muted/50 border border-border">
													<div className="flex items-center justify-between mb-2">
														<h4 className="font-medium">{profile.name}</h4>
														<Badge variant="terminal">{profile.duration}</Badge>
													</div>
													<p className="text-sm text-muted-foreground">{profile.description}</p>
												</div>
											</TabsContent>
										))}
									</Tabs>
								</div>
							</CardContent>
						</Card>

						{/* Advanced Options */}
						<Card variant="terminal">
							<CardHeader>
								<CardTitle className="flex items-center gap-2 text-lg">
									<Settings className="h-5 w-5" />
									Agent Configuration
								</CardTitle>
								<CardDescription>Override global settings for this specific scan</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4 pt-6">
								<div className="flex items-center justify-between p-4 rounded-lg border border-border">
									<div className="space-y-0.5">
										<Label className="text-base">RAG Intelligence</Label>
										<p className="text-xs text-muted-foreground">Query ChromaDB for CVE context during analysis</p>
									</div>
									<Switch
										checked={advancedOptions.enableRAG}
										onCheckedChange={(checked) => setAdvancedOptions((prev) => ({ ...prev, enableRAG: checked }))}
										aria-label="Toggle RAG Intelligence"
										disabled={createScanMutation.isPending}
									/>
								</div>

								<div className="flex items-center justify-between p-4 rounded-lg border border-border">
									<div className="space-y-0.5">
										<Label className="text-base">Circuit Breaker</Label>
										<p className="text-xs text-muted-foreground">Abort after 3 consecutive failures to prevent loops</p>
									</div>
									<Switch
										checked={advancedOptions.circuitBreaker}
										onCheckedChange={(checked) => setAdvancedOptions((prev) => ({ ...prev, circuitBreaker: checked }))}
										aria-label="Toggle Circuit Breaker"
										disabled={createScanMutation.isPending}
									/>
								</div>

								<div className="flex items-center justify-between p-4 rounded-lg border border-border">
									<div className="space-y-0.5">
										<Label className="text-base">Graph Memory</Label>
										<p className="text-xs text-muted-foreground">Store attack paths in Neo4j for visualization</p>
									</div>
									<Switch
										checked={advancedOptions.graphMemory}
										onCheckedChange={(checked) => setAdvancedOptions((prev) => ({ ...prev, graphMemory: checked }))}
										aria-label="Toggle Graph Memory"
										disabled={createScanMutation.isPending}
									/>
								</div>

								<div className="flex items-center justify-between p-4 rounded-lg border border-border">
									<div className="space-y-0.5">
										<Label className="text-base">Self-Healing</Label>
										<p className="text-xs text-muted-foreground">LLM rewrites failed scripts automatically</p>
									</div>
									<Switch
										checked={advancedOptions.autoHeal}
										onCheckedChange={(checked) => setAdvancedOptions((prev) => ({ ...prev, autoHeal: checked }))}
										aria-label="Toggle Self-Healing"
										disabled={createScanMutation.isPending}
									/>
								</div>
							</CardContent>
						</Card>
					</div>

					{/* Launch Panel */}
					<div className="space-y-6">
						<Card className="bg-gradient-to-br from-primary/10 to-background border-primary/30">
							<CardHeader>
								<CardTitle>Launch Scan</CardTitle>
								<CardDescription>Review your configuration and start the assessment.</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="p-4 rounded-lg bg-muted/50 border border-border text-sm space-y-2">
									<div className="flex justify-between">
										<span className="text-muted-foreground">Target:</span>
										<span className="font-mono truncate">{target || "Not set"}</span>
									</div>
									<div className="flex justify-between">
										<span className="text-muted-foreground">Profile:</span>
										<span className="font-medium">{scanProfiles.find((p) => p.id === scanProfile)?.name}</span>
									</div>
								</div>
								<Button
									size="lg"
									className="w-full"
									onClick={handleStartScan}
									disabled={!target.trim() || createScanMutation.isPending}
								>
									{createScanMutation.isPending ? (
										<Loader2 className="h-5 w-5 mr-2 animate-spin" />
									) : (
										<Play className="h-5 w-5 mr-2" />
									)}
									{createScanMutation.isPending ? "Initiating..." : "Start Scan"}
								</Button>
							</CardContent>
						</Card>
					</div>
				</div>
			</div>
		</Layout>
	);
}

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Layout } from "@/components/layout/Layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AlertTriangle, Search, Filter, ExternalLink, Download, Loader2 } from "lucide-react";
import { vulnerabilitiesAPI, Vulnerability, VulnerabilitySeverityBreakdown } from "@/lib/api";
import { useDebounce } from "@/hooks/use-debounce";
import { usePersistentState } from "@/hooks/use-persistent-state";
import { format } from "date-fns";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/components/ui/pagination";

const severityColors: Record<string, { text: string; border: string; bg: string; }> = {
	critical: { text: "text-destructive", border: "border-destructive/30", bg: "bg-destructive/5" },
	high: { text: "text-orange-400", border: "border-orange-500/30", bg: "bg-orange-500/5" },
	medium: { text: "text-warning", border: "border-warning/30", bg: "bg-warning/5" },
	low: { text: "text-primary", border: "border-primary/30", bg: "bg-primary/5" },
	info: { text: "text-muted-foreground", border: "border-border", bg: "bg-muted/20" },
};

export default function VulnerabilitiesPage() {
	const [searchQuery, setSearchQuery] = usePersistentState("vulnerabilities:search", "");
	const debouncedSearch = useDebounce(searchQuery, 300);
	const [severityFilter, setSeverityFilter] = usePersistentState<string>("vulnerabilities:severity", "all");
	const [statusFilter, setStatusFilter] = usePersistentState<string>("vulnerabilities:status", "all");
	const [currentPage, setCurrentPage] = usePersistentState<number>("vulnerabilities:page", 1);
	const itemsPerPage = 10;

	const { data: statsData, isLoading: isLoadingStats } = useQuery({
		queryKey: ["vulnerabilityStats"],
		queryFn: vulnerabilitiesAPI.stats,
	});

	const severityStats = statsData?.by_severity;
	const totalStats = statsData?.total ?? 0;

	const { data: vulnsData, isLoading: isLoadingVulns } = useQuery({
		queryKey: ["vulnerabilities", currentPage, debouncedSearch, severityFilter, statusFilter],
		queryFn: () => vulnerabilitiesAPI.list({
			skip: (currentPage - 1) * itemsPerPage,
			limit: itemsPerPage,
			search: debouncedSearch,
			severity: severityFilter !== "all" ? severityFilter : undefined,
			status: statusFilter !== "all" ? statusFilter : undefined,
		}),
		placeholderData: (previousData) => previousData,
	});

	const vulnerabilities = vulnsData?.vulnerabilities || [];
	const totalCount = vulnsData?.total || 0;
	const totalPages = Math.ceil(totalCount / itemsPerPage);

	useEffect(() => {
		if (totalPages === 0 && currentPage !== 1) {
			setCurrentPage(1);
		} else if (totalPages > 0 && currentPage > totalPages) {
			setCurrentPage(totalPages);
		}
	}, [currentPage, setCurrentPage, totalPages]);

	const handlePageChange = (page: number) => {
		if (page >= 1 && page <= totalPages) {
			setCurrentPage(page);
		}
	};

	const getCvssColor = (score: number | string | null) => {
		const numScore = typeof score === 'string' ? parseFloat(score) : score;
		if (numScore === null || isNaN(numScore)) return "text-muted-foreground";
		if (numScore >= 9.0) return "text-destructive";
		if (numScore >= 7.0) return "text-orange-400";
		if (numScore >= 4.0) return "text-warning";
		return "text-primary";
	};

	return (
		<Layout>
			<div className="container mx-auto px-4 py-8">
				{/* Header */}
				<div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
					<div className="flex items-center gap-3">
						<div className="p-2 rounded-lg bg-destructive/10 border border-destructive/30">
							<AlertTriangle className="h-6 w-6 text-destructive" />
						</div>
						<div>
							<h1 className="text-2xl font-bold">Vulnerability Findings</h1>
							<p className="text-muted-foreground text-sm">Discovered vulnerabilities across all scans</p>
						</div>
					</div>
					<Button variant="default">
						<Download className="h-4 w-4 mr-2" />
						Export Report
					</Button>
				</div>

				{/* Stats Cards */}
				<div className="grid grid-cols-2 lg:grid-cols-6 gap-4 mb-6">
					<Card className="border-primary/30 bg-primary/5">
						<CardContent className="pt-6">
							{isLoadingStats ? <Loader2 className="h-6 w-6 animate-spin" /> : (
								<p className="text-3xl font-bold text-primary">{totalStats}</p>
							)}
							<p className="text-sm text-muted-foreground">Total</p>
						</CardContent>
					</Card>
					{Object.entries(severityColors).map(([key, value]) => (
						<Card key={key} className={`${value.border} ${value.bg}`}>
							<CardContent className="pt-6">
								{isLoadingStats ? <Loader2 className="h-6 w-6 animate-spin" /> : (
									<p className={`text-3xl font-bold ${value.text}`}>{severityStats?.[key as keyof VulnerabilitySeverityBreakdown] ?? 0}</p>
								)}
								<p className="text-sm text-muted-foreground capitalize">{key}</p>
							</CardContent>
						</Card>
					))}
				</div>

				{/* Filters */}
				<Card variant="glow" className="mb-6">
					<CardContent className="pt-6">
						<div className="flex flex-col lg:flex-row gap-4">
							<div className="relative flex-1">
								<Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
								<Input
									placeholder="Search by CVE, title, or target..."
									value={searchQuery}
									onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
									className="pl-10"
									aria-label="Search vulnerabilities"
								/>
							</div>
							<Select value={severityFilter} onValueChange={(v) => { setSeverityFilter(v); setCurrentPage(1); }}>
								<SelectTrigger className="w-full lg:w-[180px]" aria-label="Filter by severity">
									<Filter className="h-4 w-4 mr-2" />
									<SelectValue placeholder="Severity" />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="all">All Severities</SelectItem>
									<SelectItem value="critical">Critical</SelectItem>
									<SelectItem value="high">High</SelectItem>
									<SelectItem value="medium">Medium</SelectItem>
									<SelectItem value="low">Low</SelectItem>
									<SelectItem value="info">Info</SelectItem>
								</SelectContent>
							</Select>
							<Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setCurrentPage(1); }}>
								<SelectTrigger className="w-full lg:w-[180px]" aria-label="Filter by status">
									<SelectValue placeholder="Status" />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="all">All Status</SelectItem>
									<SelectItem value="open">Open</SelectItem>
									<SelectItem value="confirmed">Confirmed</SelectItem>
									<SelectItem value="remediated">Remediated</SelectItem>
									<SelectItem value="false_positive">False Positive</SelectItem>
								</SelectContent>
							</Select>
						</div>
					</CardContent>
				</Card>

				{/* Table */}
				<Card variant="terminal">
					<CardContent className="p-0">
						<div className="overflow-x-auto">
							<Table>
								<TableHeader>
									<TableRow className="border-border hover:bg-transparent">
										<TableHead className="w-[140px]">CVE ID</TableHead>
										<TableHead>Title</TableHead>
										<TableHead className="w-[100px]">Severity</TableHead>
										<TableHead className="w-[140px]">Target</TableHead>
										<TableHead className="w-[120px]">Port</TableHead>
										<TableHead className="w-[120px]">Status</TableHead>
										<TableHead className="w-[80px]">CVSS</TableHead>
										<TableHead className="w-[180px]">Discovered</TableHead>
										<TableHead className="w-[50px]"></TableHead>
									</TableRow>
								</TableHeader>
								<TableBody>
									{isLoadingVulns && (
										<TableRow>
											<TableCell colSpan={9} className="h-24 text-center">
												<Loader2 className="mx-auto h-6 w-6 animate-spin" />
											</TableCell>
										</TableRow>
									)}
									{!isLoadingVulns && vulnerabilities.length === 0 && (
										<TableRow>
											<TableCell colSpan={9} className="h-24 text-center text-muted-foreground">
												No vulnerabilities found for the current filters.
											</TableCell>
										</TableRow>
									)}
									{!isLoadingVulns && vulnerabilities.map((vuln: Vulnerability) => (
										<TableRow key={vuln.id} className="border-border hover:bg-muted/50 cursor-pointer">
											<TableCell className="font-mono text-primary">{vuln.cve || "N/A"}</TableCell>
											<TableCell className="font-medium">{vuln.title}</TableCell>
											<TableCell>
												<Badge variant={vuln.severity as any}>{vuln.severity}</Badge>
											</TableCell>
											<TableCell className="font-mono text-sm">{vuln.target}</TableCell>
											<TableCell className="font-mono text-sm text-muted-foreground">{vuln.port}</TableCell>
											<TableCell>
												<Badge variant={vuln.status === "remediated" ? "success" : vuln.status === "confirmed" ? "info" : "secondary"}>
													{vuln.status.replace(/_/g, ' ')}
												</Badge>
											</TableCell>
											<TableCell className={`font-mono font-bold ${getCvssColor(vuln.cvss_score)}`}>
												{vuln.cvss_score ? parseFloat(vuln.cvss_score).toFixed(1) : "N/A"}
											</TableCell>
											<TableCell className="text-sm text-muted-foreground">
												{format(new Date(vuln.discovered_at), "MMM d, yyyy")}
											</TableCell>
											<TableCell>
												<Button variant="ghost" size="icon" asChild>
													<a href={vuln.references?.[0]} target="_blank" rel="noopener noreferrer" aria-label="View CVE details">
														<ExternalLink className="h-4 w-4" />
													</a>
												</Button>
											</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>
						</div>

						{/* Pagination */}
						{totalPages > 1 && (
							<div className="flex items-center justify-between p-4 border-t border-border">
								<p className="text-sm text-muted-foreground">
									Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, totalCount)} of {totalCount} findings
								</p>
								<Pagination>
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
							</div>
						)}
					</CardContent>
				</Card>
			</div>
		</Layout>
	);
}

# Trinity Viva — Strict Judge Question Bank (Practice)

Use these to rehearse. The best answers reference *your implementation choices* (Celery background scans, guard scope checks, Chroma RAG, Neo4j graph hygiene).

## A) Agent definition & architecture

1. Define “agent” vs “chatbot” in one sentence. Why is Trinity an agent?
2. What are the four roles in your pipeline (Planner/Guard/Executor/Observer) and why split them?
3. What makes your system **stateful**? Where is state stored?
4. Where does the LLM sit in the architecture? Is it required for every scan?
5. What happens if the LLM is down? What does your system do?

## B) Safety, scope, and ethics

6. How do you enforce scope (subnet restriction) at runtime?
7. What do you block (examples) and why?
8. Why is a deterministic guard stronger than “prompt-only safety”?
9. What is your circuit breaker and what failure mode does it prevent?

## C) Tooling and execution

10. Which pentesting tools are installed inside your Docker image? Which categories (network/web/auth)?
11. Why is installing tools in Docker important for reproducibility?
12. How are tools executed (subprocess)? How do you handle timeouts?
13. How do you parse tool output into structured data?
14. What are the biggest sources of noise/false positives in your tool outputs?

## D) CVE intelligence (Chroma / NVD)

15. Where do CVEs come from in your system?
16. How do you keep CVEs up to date?
17. Explain “vector similarity” in simple terms.
18. Exactly what text is used as the query to Chroma?
19. What does the similarity score mean? Is it proof of exploitability?
20. What is the difference between “vulnerability candidate” vs “confirmed vulnerability”?

## E) Graph memory (Neo4j)

21. What is “graph-based knowledge hygiene” and why does it matter?
22. What node types and edges do you store?
23. What happens if Neo4j is down?
24. How does the graph help the Planner avoid repeating work?

## F) n8n integration

25. Why do you use n8n instead of hardcoding notifications?
26. What events do you currently send to n8n?
27. What would you automate in the future using n8n?

## G) Evaluation & demo readiness

28. What are your evaluation metrics and what improved vs baseline?
29. What are the system limitations today (be honest)?
30. If you had 2 weeks more, what would you improve first and why?

## H) Quick “perfect” viva answers (short)

- **Agent vs chatbot**: “A chatbot talks; an agent acts. Trinity plans, executes tools, observes outputs, and persists state.”
- **Why Celery**: “So the API is responsive and scans run reliably in the background.”
- **How CVEs match**: “Observed service fingerprints become a semantic query into ChromaDB; we retrieve nearest CVEs, not hardcoded IDs.”
- **n8n**: “Automation/monitoring layer—webhooks for scan and CVE sync events; core scan doesn’t depend on it.”

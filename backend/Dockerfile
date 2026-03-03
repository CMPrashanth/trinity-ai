# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies & PENTESTING ALL-SOURCE TOOLS
# This equips the TrinityAI Sandbox with WhiteRabbitNeo's maximum supported arsenal
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    wget \
    gnupg \
    # Core Network Discovery & Protocols
    nmap \
    masscan \
    arp-scan \
    net-tools \
    dnsutils \
    iputils-ping \
    netcat-traditional \
    socat \
    whois \
    traceroute \
    # SMB & Linux Enum
    smbclient \
    ldap-utils \
    snmp \
    # Web & SSL
    nikto \
    whatweb \
    dirb \
    sslscan \
    # Brute Force & Vuln
    sqlmap \
    hydra \
    medusa \
    # Utilities
    proxychains \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

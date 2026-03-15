# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies & PENTESTING TOOLS
# Core tools available in Debian Trixie repos
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    wget \
    gnupg \
    git \
    # Core Network Discovery & Protocols
    nmap \
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
    # SSL
    sslscan \
    # Web enumeration / vuln tooling
    dirb \
    gobuster \
    whatweb \
    wfuzz \
    sqlmap \
    hydra \
    # Utilities
    proxychains4 \
    && rm -rf /var/lib/apt/lists/*

# Note: Some tools are still not in standard Debian Trixie repos:
# - nikto, dirbuster, medusa, crackmapexec, masscan, arp-scan
# Trinity AI will work without these for now.

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip first to avoid hash verification bugs in older pip versions
RUN pip install --upgrade pip

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

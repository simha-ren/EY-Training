
# HealthBridge — Application Gateway vs Load Balancer

## The Decision Rule

| | Application Gateway | Load Balancer |
|---|---|---|
| **OSI Layer** | Layer 7 (HTTP/HTTPS) | Layer 4 (TCP/UDP) |
| **Traffic type** | Web traffic — browsers, REST APIs, SOAP-over-HTTP | Any TCP/UDP — raw sockets, HL7, DICOM, SOAP-over-TCP |
| **Routing intelligence** | URL path, hostname, HTTP headers, cookies | IP + port only |
| **Security** | WAF, SSL termination, end-to-end TLS re-encryption | None — pass-through only |
| **Exposure** | Public or internal | Typically internal |
| **Latency overhead** | Small (HTTP parsing) | Near-zero |

**Ask yourself one question first:**
> Does the routing decision require reading the HTTP request — URL, hostname, or header?

If yes → **Application Gateway**. If no → **Load Balancer**.

---

## Architecture Overview

```
Internet
    │
    ├──► Application Gateway (public IP)
    │         │
    │    ┌────┴──────────────────────────────────────────────┐
    │    │  WAF + SSL Termination + Layer 7 Routing          │
    │    └────┬──────────────────┬──────────────────┬────────┘
    │         │                  │                  │
    │    /api/* pool       /static/* →         host-based
    │    Auth header       Blob Storage         routing
    │    Host routing                       (admin / www)
    │
    └──► [Internal VNet only]
              │
         Load Balancer (internal)
              │
    ┌─────────┼──────────────────┐
    │         │                  │
 Clinical   DICOM image       SOAP lab
 API VMs    processing VMs    VMs (x2)
 (x12)      (long-lived TCP)  (failover)
```

---

## Decision Breakdown

### 1. Patient Web Portal → **Application Gateway**

The portal receives public HTTPS traffic at 400,000 requests/hour and needs three Layer 7 capabilities simultaneously: WAF to block OWASP Top 10 attacks, SSL termination at the entry point so backends don't carry that burden, and URL path routing to send `/api/*` to the API pool and `/static/*` directly to Blob Storage. Any one of these alone would require Application Gateway — all three together make it the only option.

```
Browser (HTTPS 443)
    │
    ▼
Application Gateway
    ├── WAF (SQLi, XSS blocked)
    ├── SSL terminated here
    ├── /api/*     → API backend pool
    └── /static/*  → Azure Blob Storage
```

---

### 2. Clinical API — Internal HL7 Traffic → **Load Balancer**

EHR systems inside the VNet send HL7 FHIR over TCP port 8443 to 12 backend VMs. There is no public exposure, no HTTP to parse, and no routing logic needed beyond "spread load evenly." Application Gateway would add HTTP-parsing overhead that serves no purpose here. Load Balancer distributes TCP connections with sub-millisecond overhead and nothing more.

```
EHR Systems (VNet, TCP 8443)
    │
    ▼
Internal Load Balancer
    │
    ├── Clinical API VM 1
    ├── Clinical API VM 2
    └── ... VM 12
```

---

### 3. DICOM Image Streaming → **Load Balancer**

DICOM studies are 50–200 MB raw TCP transfers, not HTTP. Sessions last minutes and must stay pinned to one backend VM — session persistence is a standard Load Balancer feature (source IP affinity). Application Gateway is not designed for raw TCP and would not help here. Load Balancer handles long-lived TCP connections cleanly with no payload inspection overhead.

```
Radiology Workstation (raw TCP, long-lived)
    │
    ▼
Internal Load Balancer (source IP affinity)
    │
    ├── Image Processing VM 1  ← session pinned here
    ├── Image Processing VM 2
    └── Image Processing VM 3
```

---

### 4. Auth Service — Header-Based Routing → **Application Gateway**

Routing by the `x-Trust-ID` HTTP header is impossible without reading the HTTP request. Load Balancer never touches HTTP headers — it only sees IP and port. Application Gateway can inspect any HTTP header and route to different backend pools per value. End-to-end TLS re-encryption (SSL bridging) is also a native Application Gateway feature, satisfying the requirement that traffic is re-encrypted to the backend.

```
Login request (HTTPS)
    │
    ▼
Application Gateway
    ├── Read x-Trust-ID header
    ├── NW01 → North West backend pool (SAML config A)
    ├── SE04 → South East backend pool (SAML config B)
    └── ... 14 trust pools total
    [TLS re-encrypted to each backend]
```

---

### 5. Legacy SOAP Lab Service → **Load Balancer**

The service speaks SOAP over TCP port 9090 — not HTTP. The vendor contract prohibits touching the payload or headers, which rules out any Layer 7 device. The only requirement is: if one VM goes down, send traffic to the other. This is pure Layer 4 health-check failover, which is exactly what Load Balancer does with minimal configuration.

```
Pathology Lab Systems (TCP 9090, internal)
    │
    ▼
Internal Load Balancer (health probe on TCP 9090)
    ├── Lab VM 1  ◄── active
    └── Lab VM 2  ◄── standby / failover
```

---

### 6. Admin Dashboard — Hostname Routing → **Application Gateway**

Both `admin.healthbridge.nhs.uk` and `www.healthbridge.nhs.uk` share a single public IP. Splitting traffic by hostname requires reading the HTTP `Host` header — a Layer 7 operation. Load Balancer sees only IP and port, so it cannot distinguish between the two subdomains arriving on the same IP and port 443. Application Gateway's multi-site listeners handle this natively. Autoscaling on the backend pools is configured independently of the gateway itself.

```
Single Public IP (HTTPS 443)
    │
    ▼
Application Gateway (multi-site listeners)
    ├── Host: admin.healthbridge.nhs.uk → 2-VM admin pool
    └── Host: www.healthbridge.nhs.uk   → 6-VM public pool
```

---

## Full Solution Matrix

| # | Scenario | Decision | Deciding Factor |
|---|---|---|---|
| 1 | Patient web portal | **Application Gateway** | WAF + SSL termination + URL path routing (Layer 7) |
| 2 | Clinical API — internal HL7 | **Load Balancer** | Internal TCP only, no HTTP awareness needed |
| 3 | DICOM image streaming | **Load Balancer** | Raw TCP, long-lived sessions, source IP affinity |
| 4 | Auth service header routing | **Application Gateway** | Must read `x-Trust-ID` HTTP header (Layer 7) |
| 5 | Legacy SOAP lab service | **Load Balancer** | Internal TCP, failover only, no payload inspection |
| 6 | Admin dashboard hostname | **Application Gateway** | Must split traffic by `Host` header (Layer 7) |

---

## Quick Reference

**Reach for Application Gateway when you see:**
- WAF, OWASP, SQL injection, XSS protection
- SSL termination or end-to-end TLS
- URL path routing (`/api/*`, `/static/*`)
- Hostname routing (multiple subdomains on one IP)
- HTTP header inspection or cookie-based routing

**Reach for Load Balancer when you see:**
- TCP or UDP (not HTTP)
- Internal VNet traffic only
- Sub-millisecond / zero overhead requirement
- Simple failover between two VMs
- "Do not inspect or modify the payload"

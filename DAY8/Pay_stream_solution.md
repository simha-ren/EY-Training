# PayStream Messaging Architecture

## Overview

PayStream processes **4 million transactions per day** across 600 merchant clients. This document covers the messaging layer design — specifically, how we chose between a **Message Queue** and an **Event Bus** for each integration point.

---

## The Core Distinction

Before diving into decisions, here's the mental model:

| | Message Queue | Event Bus |
|---|---|---|
| **Semantics** | "Please do this task" | "This just happened" |
| **Consumers** | One worker owns each message | Any number of subscribers |
| **Coupling** | Sender knows a task must happen | Sender doesn't care who listens |
| **Retry** | Built-in, per message | Handled by each subscriber |
| **Use for** | Commands, jobs, work items | State changes, notifications |

---

## System Architecture

```
                      ┌──────────────────┐
                      │   Merchant API   │
                      └────────┬─────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │   API Gateway    │
                      └────────┬─────────┘
                               │
                               ▼
           ┌───────────────────────────────────────┐
           │             Payment Core              │
           │    Validation · Auth · Orchestration  │
           └──────┬────────────────────┬───────────┘
                  │                    │
             [D] Fraud            [A] Settle
              Request              Command
                  │                    │
                  ▼                    ▼
          ┌─────────────┐     ┌─────────────────┐
          │ Fraud Queue │     │  Settlement Queue│
          └──────┬──────┘     └────────┬─────────┘
                 │                     │
                 ▼                     ▼
         ┌─────────────┐      ┌────────────────┐
         │ Fraud Engine│      │ Ledger Service  │
         └─────────────┘      └───────┬─────────┘
                                      │
                              Payment Settled
                                      │
                                      ▼
                           ┌──────────────────────┐
                           │       Event Bus       │
                           │   (Pub/Sub Topic)     │
                           └──────┬──────┬─────┬───┘
                                  │ [B]  │ [B] │ [B]
                                  ▼      ▼     ▼
                      ┌──────────┐ ┌──────────┐ ┌──────────────┐
                      │Analytics │ │  Fraud   │ │Notification  │
                      │Pipeline  │ │ Profiler │ │     Hub      │
                      └──────────┘ └──────────┘ └──────┬───────┘
                                                        │ [C]
                                                        ▼
                                               ┌─────────────────┐
                                               │  Notify Queue   │
                                               └──┬───┬───┬──────┘
                                                  ▼   ▼   ▼
                                                 W1  W2  W3
```

```
Account Lifecycle Events

  KYC Updated / Account Suspended
               │
               ▼
        ┌────────────┐
        │  Event Bus │  [E]
        └──┬──────┬──┘
           │      │
    ┌──────┘      └──────┐
    ▼                    ▼
Payment Core       Merchant Portal
Compliance Svc     (+ any future subs)


End-of-Day Reconciliation

  600 Merchant Files
         │
         ▼
  ┌────────────┐
  │    Queue   │  [F]
  └──┬───┬──┬──┘
     ▼   ▼  ▼
    W1  W2  W3
```

---

## Decision Breakdown

### [A] Settlement Command → **Queue**

Settlement must happen **exactly once**. If the ledger service processes the same payment twice, money moves incorrectly. A queue guarantees that a message is claimed by one worker, with built-in retry if that worker crashes mid-process. An event bus would fan out the settlement to multiple consumers — exactly what we don't want here.

```
Payment Core ──► Settlement Queue ──► Ledger Service (one worker, one settlement)
```

### [B] Payment Settled Broadcast → **Event Bus**

Once a payment lands in the ledger, at least three systems need to know: analytics wants to record it, fraud profiling wants to update its model, and the notification hub wants to alert the merchant. Each service has its own reaction and its own pace. An event bus lets all of them subscribe independently — adding a fourth subscriber later requires zero changes to the publisher.

```
Ledger Service ──► Event Bus ──► [Analytics, Fraud Profiler, Notification Hub, ...]
```

### [C] SMS / Push Notifications → **Queue**

The notification hub receives a single "Payment Settled" event but may need to send hundreds of notifications (one per relevant merchant contact). These are discrete delivery tasks — each SMS or push needs to land with exactly one worker. The queue spreads load across Worker 1/2/3 and handles retries if a delivery fails (e.g. carrier timeout).

```
Notification Hub ──► Notify Queue ──► [W1 | W2 | W3] (each message delivered once)
```

### [D] Fraud Score Request → **Queue**

Fraud scoring is a synchronous-style call wrapped in async infrastructure. Payment Core sends a request; the Fraud Engine must respond with a score before authorisation can complete. This is point-to-point: one request, one scorer. A queue provides the reliable delivery channel with backpressure support if the fraud engine falls behind traffic spikes.

```
Payment Core ──► Fraud Queue ──► Fraud Engine (scores and replies)
```

### [E] Account State Changes → **Event Bus**

When KYC status updates or an account is suspended, this is a fact about the world — not a command directed at any single service. Payment Core needs to gate future transactions, the Merchant Portal needs to show updated status, and Compliance needs an audit trail. All three subscribe independently. New regulatory requirements could add a fourth subscriber without touching the account service.

```
Account Service ──► Event Bus ──► [Payment Core, Merchant Portal, Compliance, ...]
```

### [F] End-of-Day Reconciliation → **Queue**

At midnight, 600 merchant files arrive and need processing before the next trading day. This is a classic worker pool problem. Each file is an independent job; the queue distributes them across however many workers are available, retries any that fail, and lets the team scale the worker count to hit the processing deadline.

```
600 files ──► Queue ──► [W1 | W2 | W3 | ... Wn] (scale to meet deadline)
```

---

## Summary

| ID | Integration Point | Pattern | Key Reason |
|---|---|---|---|
| A | Settlement Command | **Queue** | Exactly-once, single consumer |
| B | Payment Settled Broadcast | **Event Bus** | Fan-out to multiple independent services |
| C | SMS / Push Delivery | **Queue** | Per-message delivery, load-balanced workers |
| D | Fraud Score Request | **Queue** | Point-to-point request, one scorer |
| E | Account State Change | **Event Bus** | State broadcast to many subscribers |
| F | Reconciliation Jobs | **Queue** | Worker pool distribution, retry on failure |

---

## Quick Reference

**Reach for a Queue when you're thinking:**
> "I need this specific thing done, and I don't want it done twice."

**Reach for an Event Bus when you're thinking:**
> "Something happened — I'll announce it and let whoever cares react."

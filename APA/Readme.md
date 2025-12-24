Below is an **abridged, MCP-ready context summary** of the **AVEVA Predictive Analytics Concepts Guide (v2023, Jan 2024)**, rewritten specifically so an **LLM can quickly understand the domain, architecture, data flow, and analytical logic** before you design MCP tools or Web/API contracts.

This is **not a user manual summary**—it is a **systems + analytics mental model**, optimized for tool design, reasoning, and API orchestration.

---

## 1. What AVEVA Predictive Analytics Is (Core Concept)

AVEVA Predictive Analytics (PA) is an **asset-centric anomaly detection system** that:

* Learns **normal operational behavior** of industrial equipment from **historical data**
* Builds **Operational Profiles** (statistical behavior models)
* Continuously compares **current real-time data** against those profiles
* Detects **deviations (anomalies)** and raises **alerts**
* Supports **root-cause investigation** via deviation contribution analysis

It is **not rule-based**; it is **model-driven**, using historical correlations between signals.

---

## 2. High-Level System Architecture

### Main Components

1. **Predictive Analytics Client (Desktop)**

   * Used by engineers
   * Imports historical data
   * Builds & tunes operational profiles
   * Defines points, calculations, filters, alerts
   * Performs offline and exploratory analytics

2. **Predictive Analytics Server**

   * Runs continuously
   * Compares live data vs operational profiles
   * Calculates predictions, deviations, OMR
   * Generates alerts
   * Writes results to historian & central DB

3. **Predictive Analytics Web (IIS)**

   * Read-only operational view
   * Alert dashboards, charts
   * Case management
   * Web API for external integrations

### Datastores

* **Central Database (SQL Server)**

  * Projects, profiles, configurations, alerts, metadata
* **Archive Database (Historian / PI System)**

  * Time-series outputs:

    * Actual values
    * Predicted values
    * Deviations
    * OMR

---

## 3. Core Domain Objects (Important for MCP Schema Design)

### Project

Logical container for monitoring one asset or system.

Contains:

* Project points
* Training data
* Operational profiles
* Filters
* Alerts
* Notes

### Asset Hierarchy

* Folder-like structure
* Organizes projects
* Used for navigation, permissions, alert roll-ups

---

## 4. Project Points (Signals)

### Input Point Types

* **Historian points** (PI, Historian, SQL, OPC UA)
* **Calculation points** (derived formulas)
* **Offline points** (file-imported historical data)

### Template-Level Points

* **Metrics** (abstract points mapped to real points)
* **Template calculations**

### Output Points (Model Results)

For each input point:

* **Actual** – observed value
* **Prediction** – expected value from model
* **Deviation**

  * Absolute (engineering units)
  * Relative (% of training range)
* **Contribution** – impact on overall deviation

Also:

* **Overall Model Residual (OMR)**
  → Aggregate deviation across all points (health score)

---

## 5. Operational Profiles (The Core Model)

An **Operational Profile** is a learned representation of *normal behavior*.

### Key Properties

* Built from **historical training data**
* Groups signals into **data modes**

  * Each mode = a typical operating condition
* Captures **relationships between points**, not just limits

### Runtime Behavior

* Finds the closest matching mode
* Predicts expected values
* Calculates deviations
* Aggregates deviations into OMR
* Applies thresholds → alerts

> Only **one profile is active at a time per project**, but multiple can exist.

---

## 6. Near Real-Time (NRT) Processing

### Why NRT Exists

Handles:

* Network outages
* Server downtime
* Intermittent data
* Batch uploads (mobile assets)

### How NRT Works

* Server tracks **last processed timestamp**
* If multiple new data points arrive:

  * Requests historical batches
  * Back-processes data
* Enforces **Max History Request Size** for performance control

### Implication for Tooling

* Profiles can “flatline” visually while backfilling
* MCP tools must distinguish:

  * Real-time vs backfill vs stale processing states

---

## 7. Data Quality Model

Data quality is **first-class**, not optional.

### Quality Handling

* Each data point evaluated for:

  * Timestamp validity
  * Historian-specific rules
* Bad data:

  * Excluded from training
  * Can auto-close alerts
  * Can trigger recovery logic

### Quality Affects:

* Calculations
* Training datasets
* Operational profile execution
* Alert lifecycle

---

## 8. Alerts & Notifications

### Alert Triggers

* Point deviation thresholds
* OMR thresholds
* Persistence windows (time-based)

### Alert Lifecycle

* Open
* Persist
* Escalate (tiered notifications)
* Clear
* Assign to cases

### Alert Outputs

* Stored in Central DB
* Exposed via Web UI & Web API
* Optional email notifications (SMTP)

---

## 9. Fault Diagnostics & Root Cause

Beyond detection, PA supports **diagnosis**:

* **Deviation-based fault signatures**
* **Metric contribution analysis**
* Relative vs absolute contributions
* Multi-point correlation
* Minimum deviation logic to reduce noise

This enables:

* “What failed?”
* “Which signal caused it?”
* “How confident is the diagnosis?”

---

## 10. Communication & Integration Model

### Protocols

* OPC UA / ODBC → historians
* ADO.NET → SQL Server
* HTTP(S) → Web & APIs
* SMTP → notifications

### Security

* Active Directory authentication
* Typically single-domain deployments

---

## 11. What This Means for MCP Tool Design

From an MCP perspective, AVEVA PA is:

* **Stateful**
* **Time-series driven**
* **Model-based**
* **Event + batch hybrid**
* **Quality-aware**
* **Strongly hierarchical**

### Natural MCP Tool Categories

* Project & asset discovery
* Point metadata resolution
* Operational profile status & health
* Deviation & OMR queries
* Alert lifecycle operations
* Training data inspection
* Backfill / NRT state introspection
* Fault signature explanation

---

## 12. One-Sentence Mental Model (For LLM Context)

> *AVEVA Predictive Analytics continuously compares live industrial sensor data against statistically learned models of normal behavior, detects deviations across correlated signals, aggregates them into health metrics, and manages alerts, diagnostics, and historical backfill with strong data-quality governance.*

---

If you want, next we can:

* Map this into **MCP tool taxonomy**
* Design **LLM-safe abstractions over Web API**
* Propose **tool schemas (read vs control vs diagnostic)**
* Create **LLM context window compression strategy** for production MCP servers

Just tell me the next step.


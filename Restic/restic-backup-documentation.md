# New Restic Backup System — Configuration and Recovery Workflows

**Redback Operations — GPU Server (capstone-gpu1)**  
**Prepared by:** Sandy Dissanayake (SanduniUDissanayake) and Nomalizo Mqhum (nmizzy42-ux)  
**Team:** Redback Operations — Data Warehouse Infrastructure  
**Date:** April 2026  

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Installation and Setup](#3-installation-and-setup)
4. [Backup Strategy](#4-backup-strategy)
5. [Scheduling](#5-scheduling)
6. [Retention Policy](#6-retention-policy)
7. [Disk Space Management](#7-disk-space-management)
8. [Backup Script](#8-backup-script)
9. [Restoration Procedures](#9-restoration-procedures)
10. [Summary of Services Backed Up](#10-summary-of-services-backed-up)
11. [Known Issues and Recommendations](#11-known-issues-and-recommendations)
12. [File and Path Reference](#12-file-and-path-reference)
13. [Quick Reference Commands](#13-quick-reference-commands)

---

## 1. Introduction

This document provides a comprehensive account of the Restic backup system deployed on the Redback Operations GPU server (capstone-gpu1). It details the installation process, configuration decisions, service-specific backup strategies, scheduling mechanisms, retention policies, and recovery workflows. The system was established to ensure data integrity and operational continuity across all production services running on the GPU server.

The backup system was designed with the following objectives:

- Automated and frequent backups of all critical services
- Efficient incremental storage utilising Restic deduplication capabilities
- Appropriate handling of stateful services such as databases and message queues
- A clear and tested restoration procedure

---

## 2. System Overview

### 2.1 Server Details

| Property | Value |
|---|---|
| Server Hostname | capstone-gpu1 |
| Server IP Address | 10.137.17.254 |
| Operating System | Ubuntu 22.04 LTS |
| Total Disk Size | 735 GB |
| Used Disk Space (at setup) | 601 GB (86%) |
| Available Disk Space | 99 GB |
| Backup Repository Location | `/opt/redback/restic/repo` |
| Backup Repository ID | 5952996d42 |

### 2.2 Restic Version Details

| Property | Value |
|---|---|
| Restic Version | 0.18.1 |
| Go Compiler Version | Go 1.25.1 |
| Architecture | linux/amd64 |
| Installation Method | `sudo apt install restic` (v0.12.1), then `sudo restic self-update` (v0.18.1) |
| Installation Path | `/usr/bin/restic` |

> **Note:** The initial installation via apt provided version 0.12.1, which lacked built-in compression support. The self-update command was subsequently used to upgrade to version 0.18.1, which introduced native compression (`--compression max`), improved stdin streaming, and the `--no-scan` flag essential for efficient Kafka volume backups.

---

## 3. Installation and Setup

### 3.1 Restic Installation

Restic was installed on the GPU server using the Ubuntu package manager, followed by a self-update to obtain the latest version:

```bash
sudo apt update && sudo apt install -y restic
sudo restic self-update
```

### 3.2 Repository Initialisation

The backup repository directory structure was created under `/opt/redback/restic/` with the following sub-directories:

- `/opt/redback/restic/repo` — the Restic repository where all backup snapshots are stored
- `/opt/redback/restic/logs` — directory for backup log files
- `/opt/redback/restic/scripts` — directory for backup scripts

```bash
sudo mkdir -p /opt/redback/restic/{repo,logs,scripts}
```

The Restic repository was then initialised:

```bash
sudo restic init --repo /opt/redback/restic/repo --password-file /opt/redback/restic/restic-password.txt
```

### 3.3 Password and Credentials Management

The Restic repository password is stored in a dedicated password file with restricted permissions. MongoDB authentication credentials are stored in a separate environment file to prevent exposure within the backup script.

| File | Path | Permissions | Purpose |
|---|---|---|---|
| Restic Password File | `/opt/redback/restic/restic-password.txt` | 600 (root only) | Restic repository encryption password |
| Environment File | `/opt/redback/restic/.env` | 600 (root only) | MongoDB authentication credentials |
| Backup Script | `/opt/redback/restic/scripts/backup.sh` | 755 (executable) | Main backup automation script |

The environment file is sourced at the beginning of the backup script using the `source` directive, ensuring that credentials are never hardcoded directly within the script.

---

## 4. Backup Strategy

### 4.1 Overview

The backup system employs a multi-stage strategy that accounts for the different characteristics of each service. Services are categorised into three groups: databases requiring logical dumps, message queues requiring definition exports, and file or configuration-based services that can be backed up directly via Restic.

### 4.2 Service-Specific Backup Methods

#### 4.2.1 Databases

Databases cannot be backed up by directly copying their data files whilst running, as this risks producing inconsistent or corrupted backups. The dump-and-pipe strategy streams backup data directly from the database process into Restic without writing intermediate files to disk.

| Service | Container | Method | Command |
|---|---|---|---|
| MongoDB | mongodb | mongodump piped to Restic stdin | `docker exec mongodb mongodump --username redback --authenticationDatabase admin --archive \| restic backup --stdin` |
| PostgreSQL (Supabase) | supabase-db | pg_dump piped to Restic stdin | `docker exec supabase-db pg_dump -U postgres -Fc postgres \| restic backup --stdin` |

#### 4.2.2 Message Queues

| Service | Container | Method | Notes |
|---|---|---|---|
| RabbitMQ | rabbitmq | Export definitions JSON piped to Restic stdin | Captures queues, exchanges, users and permissions. No service interruption required. |
| Kafka | kafka | Direct volume backup with `--no-scan` flag | Backs up three Kafka data volumes. The `--no-scan` flag improves performance on large log segments. |

#### 4.2.3 File and Configuration-Based Services

| Service | Backup Source | Tag | Frequency |
|---|---|---|---|
| All /opt/redback services | `/opt/redback` (with exclusions) | configs | Every 4 minutes |
| Grafana | `/var/lib/docker/volumes/grafana_grafana_data/_data` | grafana | Every 4 minutes |
| Portainer | `/var/lib/docker/volumes/portainer_data/_data` | portainer | Every 4 minutes |
| Wazuh Configs (small) | 10 small Wazuh volumes (~4 MB total) | wazuh-config | Every 4 minutes |
| Wazuh Data (large) | wazuh_logs, wazuh_queue, wazuh-indexer-data (~89 GB) | wazuh-data | Daily at 2:00 AM |

### 4.3 Exclusions

The following paths are explicitly excluded from the `/opt/redback` backup:

| Excluded Path | Reason |
|---|---|
| `/opt/redback/restic` | The backup repository itself — backing this up would cause circular redundancy |
| `/opt/redback/wazuh` | Wazuh is already backed up separately via Docker volumes |
| `/opt/redback/LocalAGI/volumes/models` | AI model files (75 GB) — re-downloadable, no unique data |
| `/opt/redback/LocalAGI/volumes/backends` | Backend binaries (5.7 GB) — re-downloadable |

> The LocalAGI sub-directories `localagi/`, `localrag/`, and `images/` are included in the backup as they contain user-generated configuration and RAG data that cannot be recovered if lost.

---

## 5. Scheduling

### 5.1 Systemd Timer Configuration

The backup system is scheduled using a systemd timer rather than a cron job. Systemd timers prevent job overlap — a new backup run will not commence whilst a previous run is still executing. This is essential given the 4-minute backup frequency.

#### Service Unit File

Location: `/etc/systemd/system/restic-backup.service`

```ini
[Unit]
Description=Restic Backup Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/opt/redback/restic/scripts/backup.sh
User=root
```

#### Timer Unit File

Location: `/etc/systemd/system/restic-backup.timer`

```ini
[Unit]
Description=Run Restic Backup Every 4 Minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=4min
AccuracySec=1s

[Install]
WantedBy=timers.target
```

The timer was enabled using:

```bash
sudo systemctl daemon-reload
sudo systemctl enable restic-backup.timer
sudo systemctl start restic-backup.timer
```

---

## 6. Retention Policy

The retention policy is applied at the end of each backup run:

```bash
restic forget --keep-last 15 --keep-hourly 24 --prune
```

| Flag | Meaning |
|---|---|
| `--keep-last 15` | Retains the 15 most recent snapshots — equivalent to the last 60 minutes at 4-minute intervals |
| `--keep-hourly 24` | Retains one snapshot per hour for the last 24 hours |
| `--prune` | Immediately removes unreferenced data from the repository |

> This policy does not affect live service data in any way. It only manages snapshots within the Restic backup repository.

---

## 7. Disk Space Management

### 7.1 Current Disk Status

At the time of setup, the GPU server disk was at **86% capacity** (601 GB used of 735 GB total, with 99 GB remaining). This was identified as a significant concern and communicated to the technical lead.

### 7.2 Automated Disk Space Warning

A disk space check is executed prior to any backup operations:

| Threshold | Action |
|---|---|
| 80% or above | Warning written to log: `WARNING: Disk usage at X% — please free up space soon!` |
| 90% or above | Backup aborted: `CRITICAL: Disk usage at X% — backup aborted to prevent corruption!` |

The warning was confirmed active at the time of testing:

```
[03:54:53] WARNING: Disk usage at 86% — please free up space soon!
```

---

## 8. Backup Script

The complete backup script is located at `/opt/redback/restic/scripts/backup.sh`.

### Key Variables

| Variable | Value | Purpose |
|---|---|---|
| `REPO` | `/opt/redback/restic/repo` | Path to the Restic repository |
| `PASSWORD_FILE` | `/opt/redback/restic/restic-password.txt` | Path to the repository password file |
| `LOG` | `/opt/redback/restic/logs/backup.log` | Path to the backup log file |
| `MONGO_PASSWORD` | Sourced from `/opt/redback/restic/.env` | MongoDB authentication password |

### Script Structure

The script is organised into five stages:

- **Stage 1** — Database dumps (MongoDB, PostgreSQL)
- **Stage 2** — Message queue exports (RabbitMQ, Kafka)
- **Stage 3** — File and config-based backups (`/opt/redback`, Grafana, Portainer)
- **Stage 4** — Wazuh backups (small configs every 4 minutes, large data daily at 2 AM)
- **Stage 5** — Retention policy enforcement

---

## 9. Restoration Procedures

### 9.1 Listing Available Snapshots

```bash
sudo restic -r /opt/redback/restic/repo \
  --password-file /opt/redback/restic/restic-password.txt \
  snapshots --tag <tag>
```

Replace `<tag>` with the service name: `grafana`, `mongodb`, `supabase`, `kafka`, `rabbitmq`, `wazuh-config`, `wazuh-data`, `portainer`, or `configs`.

### 9.2 Restoring a Snapshot

```bash
sudo restic -r /opt/redback/restic/repo \
  --password-file /opt/redback/restic/restic-password.txt \
  restore <SNAPSHOT_ID> --target /tmp/restore-test
```

> It is strongly recommended to restore to a temporary directory first to verify data integrity before overwriting any live data.

### 9.3 Restoration Test Results

A restoration test was conducted on the Grafana backup to validate end-to-end integrity:

| Test Parameter | Result |
|---|---|
| Snapshot Selected | 32b21c05 (2026-04-03 03:43:15) |
| Restore Target | `/tmp/grafana-restore-test` |
| Files Restored | 384 files and directories |
| Data Volume Restored | 46.715 MiB |
| Restoration Duration | Under 1 second |
| grafana.db Present | Yes — 2.5 MB |
| Live Grafana Service Affected | No |
| **Test Result** | **PASSED** ✅ |

---

## 10. Summary of Services Backed Up

| Service | Container | Method | Frequency | Status |
|---|---|---|---|---|
| MongoDB | mongodb | mongodump via stdin | Every 4 min | ✅ Active |
| PostgreSQL/Supabase | supabase-db | pg_dump via stdin | Every 4 min | ✅ Active |
| RabbitMQ | rabbitmq | Definition export via stdin | Every 4 min | ✅ Active |
| Kafka | kafka | Volume backup (--no-scan) | Every 4 min | ✅ Active |
| Grafana | grafana | Volume backup | Every 4 min | ✅ Active |
| Portainer | portainer | Volume backup | Every 4 min | ✅ Active |
| Wazuh Configs | wazuh | 10 small volumes | Every 4 min | ✅ Active |
| Wazuh Data | wazuh | 3 large volumes | Daily at 2 AM | ✅ Active |
| /opt/redback | All services | Directory backup with exclusions | Every 4 min | ✅ Active |
| Streamlit/Flask | streamlit-app | Included in /opt/redback | Every 4 min | ✅ Active |
| LocalAGI (config/RAG) | localagi | Included in /opt/redback | Every 4 min | ✅ Active |
| LocalAGI Models | localagi | EXCLUDED — re-downloadable | N/A | ⛔ Excluded |
| Serverpage | serverpage | No persistent data | N/A | ➖ Not required |

---

## 11. Known Issues and Recommendations

### 11.1 Disk Space

At the time of setup, the GPU server disk was at 86% capacity. The automated disk check will abort backups at 90% usage. It is recommended that the technical lead investigates options for expanding available storage or relocating the backup repository to a dedicated disk or external storage solution.

### 11.2 Wazuh Large Volume Backup Duration

The three large Wazuh volumes total approximately 89 GB. The daily backup of these volumes may take considerable time on the first run. Subsequent runs will benefit from Restic's incremental deduplication, backing up only changed data blocks.

### 11.3 Streamlit and Flask

At the time of writing, the Streamlit and Flask services were moved to `/opt/redback` and are now included in the automated backup. It is recommended that these services also maintain their codebase in the team GitHub repository as a secondary backup measure.

---

## 12. File and Path Reference

| File / Directory | Path | Purpose |
|---|---|---|
| Restic Executable | `/usr/bin/restic` | Restic binary |
| Backup Repository | `/opt/redback/restic/repo` | All backup snapshots stored here |
| Password File | `/opt/redback/restic/restic-password.txt` | Repository encryption password |
| Environment File | `/opt/redback/restic/.env` | Service credentials (MongoDB password) |
| Backup Script | `/opt/redback/restic/scripts/backup.sh` | Main backup automation script |
| Backup Log | `/opt/redback/restic/logs/backup.log` | Timestamped log of all backup runs |
| Systemd Service | `/etc/systemd/system/restic-backup.service` | Systemd service unit |
| Systemd Timer | `/etc/systemd/system/restic-backup.timer` | Systemd timer unit (4-minute schedule) |

---

## 13. Quick Reference Commands

```bash
# Check timer status
sudo systemctl status restic-backup.timer

# Run backup manually
sudo systemctl start restic-backup.service

# View backup logs
cat /opt/redback/restic/logs/backup.log | tail -50

# List all snapshots
sudo restic -r /opt/redback/restic/repo --password-file /opt/redback/restic/restic-password.txt snapshots

# List snapshots by service tag
sudo restic -r /opt/redback/restic/repo --password-file /opt/redback/restic/restic-password.txt snapshots --tag <tag>

# Restore a snapshot
sudo restic -r /opt/redback/restic/repo --password-file /opt/redback/restic/restic-password.txt restore <SNAPSHOT_ID> --target /tmp/restore-dir

# Check disk usage
df -h /opt/redback/restic/repo

# Stop backup timer
sudo systemctl stop restic-backup.timer

# Start backup timer
sudo systemctl start restic-backup.timer
```

---

*This document was prepared by Sandy Dissanayake and Nomalizo Mqhum as part of the Redback Operations infrastructure migration and backup setup for Trimester 1, 2026. It is intended for internal use and may be updated as the backup system evolves.*

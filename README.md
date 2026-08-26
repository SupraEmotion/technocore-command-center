# Technocore Command Center

Open-source monitoring, research, and operations toolkit for the Technocore agent ecosystem.

## Goals

- Monitor public Technocore room activity efficiently.
- Use sequence cursors and long-polling rather than tight polling.
- Collect reproducible research data.
- Analyse agent activity patterns.
- Provide useful operational visibility for Technocore participants.

## Current research

### Research #001 — Sequence-Based Activity Monitoring

Initial experiments investigate:

- signed DID participation
- room sequence cursors
- `read --since`
- long-polling with `--wait`
- public activity patterns
- reproducible evidence collection

## Security

Private identities, keys, credentials, databases, logs, and local environment files must never be committed to this repository.

## Status

Early research / experimental software.

# PT Medical Ticketing System

## Overview

The PT Medical Ticketing System is a cloud-native healthcare management application designed for physical therapists. The application allows therapists to securely create accounts, manage patients, submit visit tickets, and track visit history through a web dashboard.

The system was designed using a distributed cloud architecture on Google Cloud Platform (GCP). Instead of using a single monolithic server, the project separates responsibilities across multiple cloud services including Cloud Run, Cloud SQL, Pub/Sub, Cloud Functions, and Firebase Authentication.

This architecture improves scalability, modularity, reliability, and fault isolation while demonstrating modern cloud-native design principles.

Important note: I intended to make the project compliant with HIPPA guidelines for storing medical infromation but it is outside my realm of knolledge and the scope of this project. 

---

# Application Features

- Therapist account creation
- Firebase Authentication login system
- Multi-user therapist isolation
- Patient creation and management
- Visit ticket submission
- Visit history tracking
- Persistent PostgreSQL storage
- Event-driven processing using Pub/Sub
- Background Cloud Function worker
- High pain-level alert processing

---

# Cloud Architecture

## Services Used

| Service | Purpose |
|---|---|
| Google Cloud Run | Hosts the Flask web application |
| Google Cloud SQL (PostgreSQL) | Persistent relational database |
| Google Cloud Pub/Sub | Event messaging system |
| Google Cloud Functions | Background asynchronous processing |
| Firebase Authentication | User authentication and login |

---

# Cost Breakdown

## Estimated Monthly Cost
|---|---|
| Service | Estimated Cost |
| Cloud Run	| $0 - $5 |
| Cloud SQL PostgreSQL | $7 - $15 |
| Pub/Sub	| Less than $1 |
| Cloud Functions	| Less than $1 |
| Firebase Authentication	| Free Tier |

---

# System Architecture Diagram

```text
                        ┌─────────────────────┐
                        │     User Browser    │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │ Firebase Auth Login │
                        └──────────┬──────────┘
                                   │ JWT Token
                                   ▼
                        ┌─────────────────────┐
                        │   Cloud Run App     │
                        │     Flask Server    │
                        └──────────┬──────────┘
                                   │
                 ┌─────────────────┴─────────────────┐
                 │                                   │
                 ▼                                   ▼
      ┌─────────────────────┐           ┌─────────────────────┐
      │     Cloud SQL       │           │    Pub/Sub Topic    │
      │   PostgreSQL DB     │           │ visit-ticket-events │
      └─────────────────────┘           └──────────┬──────────┘
                                                    │
                                                    ▼
                                       ┌─────────────────────┐
                                       │  Cloud Function     │
                                       │ process_visit_ticket│
                                       └─────────────────────┘

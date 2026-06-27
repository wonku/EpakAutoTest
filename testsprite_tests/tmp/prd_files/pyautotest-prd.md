# Pyautotest - CRM API Automation PRD

## Overview
Pyautotest is a Python-based test automation framework for YSB CRM platform. It validates member authentication and CRM 2.0 sales lead APIs against the staging environment.

## Target Environment
- Auth API: https://test-auth.ysbpack.com
- Platform API: https://test-platform.ysbpack.com

## Core Features

### 1. Member Login
- POST /api/member/login with account and encrypted password
- Returns token, memberId, userId
- Success code: response contains valid token

### 2. Sales Lead CRUD
- Create lead via POST /api/crm/lead/saveOrUpdate
- Query leads via POST /api/crm/lead/page
- Success code: 1000

### 3. Lead Lifecycle Operations
- Claim leads: POST /api/crm/lead/claimLead
- Assign leads: POST /api/crm/lead/assign
- Move to public sea: POST /api/crm/lead/movePublicSea

### 4. Activity Records
- Create activity: POST /api/crm/common/activity/saveOrUpdate
- Requires relationId from created lead

### 5. Reference Data
- Country list: GET /api/crm/common/country/list
- Effective users: GET /api/member/user/effective/list

## Authentication
All CRM APIs require headers: token, memberId, userId, environment, site, source

## Success Criteria
- Login returns valid token
- Lead creation returns code 1000
- Lead query returns matching records
- Claim/assign/move operations return code 1000

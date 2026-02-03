# User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Managing Leads](#managing-leads)
4. [Managing Documents](#managing-documents)
5. [Managing Tasks](#managing-tasks)
6. [Monitoring & Alerts](#monitoring--alerts)
7. [Security & Settings](#security--settings)
8. [Troubleshooting](#troubleshooting)
9. [FAQ](#faq)

---

## Getting Started

### Accessing the System

**URLs:**
- **Main Dashboard:** http://your-domain.com
- **n8n Workflow Editor:** http://your-domain.com (requires admin login)
- **Monitoring Dashboard:** http://your-domain.com/monitoring
- **Task Dashboard:** http://your-domain.com/tasks

**Login Credentials:**
- Username: Provided by your administrator
- Password: Provided by your administrator

### First Time Setup

1. **Log in to the system**
2. **Verify your client configuration**
3. **Review enabled automation packs**
4. **Configure notification preferences**
5. **Set up team members (if applicable)**

---

## Dashboard Overview

### Main Dashboard

The main dashboard provides an overview of your automation activities:

**Key Sections:**
- **System Health** - Overall system status
- **Recent Activity** - Latest workflow executions
- **Quick Stats** - Key metrics at a glance
- **Active Alerts** - Important notifications

### Navigation

**Main Menu:**
- **Home** - Dashboard overview
- **Leads** - Lead management
- **Documents** - Document processing
- **Tasks** - Task management
- **Monitoring** - System monitoring
- **Settings** - Configuration

---

## Managing Leads

### Lead Capture

Leads are automatically captured from multiple sources:

**Supported Sources:**
- Website forms
- Email submissions
- API integrations
- Manual entry
- CSV imports

### Viewing Leads

**Access:** Navigate to Leads section

**Lead List View:**
- Filter by status (new, enriched, routed)
- Sort by date, score, or status
- Search by email or name
- Export to CSV

**Lead Details:**
- Contact information
- Lead score (0-30 points)
- Enrichment data
- Activity history
- Routing status

### Lead Statuses

| Status | Description |
|--------|-------------|
| New | Just captured, awaiting processing |
| Processing | Being normalized and scored |
| Enriched | Email validated, company data added |
| Routed | Sent to destination system |
| Duplicate | Identified as duplicate |
| Error | Processing failed |

### Lead Scoring

Leads are automatically scored based on completeness:

**Scoring Breakdown:**
- Email present: 10 points
- First name: 5 points
- Last name: 5 points
- Company: 5 points
- Phone: 5 points

**Score Ranges:**
- 0-10: Low quality
- 11-20: Medium quality
- 21-30: High quality

### Lead Routing

High-scoring leads (21+ points) are automatically routed to:
- CRM systems (via webhook)
- Sales team (via email)
- Slack channels
- Custom destinations

---

## Managing Documents

### Document Upload

**Supported Formats:**
- PDF documents
- Images (JPG, PNG)
- Word documents (DOC, DOCX)
- Excel spreadsheets (XLS, XLSX)
- Text files (TXT)

**Upload Methods:**
1. **Email:** Send to documents@your-domain.com
2. **API:** Use document ingestion webhook
3. **Manual:** Upload via web interface (future)

### Document Processing

Documents are automatically processed through these stages:

1. **Intake** - Document received and stored
2. **Classification** - Category assigned (invoice, contract, etc.)
3. **Extraction** - Data extracted from document
4. **Validation** - Extracted data validated
5. **Routing** - Sent to appropriate destination

### Document Categories

| Category | Description | Auto-Route Destination |
|----------|-------------|----------------------|
| Invoice | Financial invoices | Finance team |
| Contract | Legal contracts | Legal team |
| Resume | Job applications | HR team |
| Report | Business reports | Management |
| Form | Completed forms | Operations |
| Receipt | Purchase receipts | Accounting |
| Letter | Correspondence | Admin |
| Other | Uncategorized | Review queue |

### Document Validation

Documents receive a validation score (0-100):

**Score Ranges:**
- 70-100: High confidence (auto-routed)
- 40-69: Medium confidence (review recommended)
- 0-39: Low confidence (manual review required)

### Human Review Queue

Documents requiring review appear in the review queue:

**Review Priority:**
- Urgent: Review within 4 hours
- High: Review within 24 hours
- Medium: Review within 48 hours
- Low: Review within 72 hours

**Review Actions:**
- Approve and route
- Edit extracted data
- Reject document
- Request more information

---

## Managing Tasks

### Task Creation

Tasks are created automatically from:
- New leads (follow-up tasks)
- Documents (processing tasks)
- Manual creation
- API integrations

### Task Assignment

Tasks are intelligently assigned based on:

**Assignment Factors:**
1. **Workload** - Current task count
2. **Skills** - Required skills matching
3. **Priority** - Task priority level
4. **Availability** - Team member availability

**Assignment Score:**
- Workload availability: 10 points per free slot
- Skills match: +20 points
- Priority weighting: +15 (urgent), +10 (high), +5 (medium)

### Task Statuses

| Status | Description |
|--------|-------------|
| Created | Task created, awaiting assignment |
| Assigned | Assigned to team member |
| In Progress | Being worked on |
| Completed | Finished successfully |
| Cancelled | Cancelled by user |
| Expired | Passed due date |

### Task Priorities

| Priority | SLA | Description |
|----------|-----|-------------|
| Critical | 4 hours | Urgent, immediate attention |
| High | 24 hours | Important, high priority |
| Medium | 48 hours | Normal priority |
| Low | 72 hours | Low priority |

### SLA Monitoring

Tasks are monitored for SLA compliance:

**SLA Levels:**
- **On Track** - Due in >4 hours
- **Warning** - Due in 1-4 hours
- **Critical** - Due in <1 hour
- **Overdue** - Past due date

**Escalation:**
- Warning alerts sent at 4 hours before due
- Critical alerts sent at 1 hour before due
- Overdue alerts sent immediately after due date

### Task Dashboard

**Access:** http://your-domain.com/tasks

**Dashboard Features:**
- Real-time task statistics
- Team performance metrics
- Filterable task list
- Priority breakdown
- SLA compliance tracking

---

## Monitoring & Alerts

### System Monitoring

**Access:** http://your-domain.com/monitoring

**Monitoring Dashboard Sections:**

1. **System Metrics**
   - Workflow execution counts
   - Success/failure rates
   - Average execution time
   - Resource utilization

2. **Business Metrics**
   - Lead counts by status
   - Document processing stats
   - Task completion rates
   - SLA compliance

3. **Active Alerts**
   - Critical alerts
   - Warning alerts
   - Alert history

4. **Recent Errors**
   - Error type and severity
   - Affected workflows
   - Error messages
   - Resolution status

5. **Dependency Health**
   - Database status
   - n8n status
   - Storage status
   - External services

### Alert Types

**System Alerts:**
- High error rate (>10%)
- System downtime
- Database issues
- Disk space warnings

**Business Alerts:**
- SLA warnings
- High DLQ count
- Processing delays
- Integration failures

### Alert Management

**Viewing Alerts:**
1. Navigate to Monitoring Dashboard
2. View Active Alerts section
3. Click alert for details

**Acknowledging Alerts:**
1. Click on alert
2. Click "Acknowledge" button
3. Add notes (optional)
4. Confirm acknowledgment

**Alert Notifications:**
- Email notifications (configured)
- Slack notifications (configured)
- Dashboard notifications (always on)

---

## Security & Settings

### Security Dashboard

**Access:** http://your-domain.com/security

**Security Features:**

1. **Credential Management**
   - View encrypted credentials
   - Add new credentials
   - Update existing credentials
   - Delete credentials

2. **Security Events**
   - Login attempts
   - Configuration changes
   - Access violations
   - System events

3. **Role Management**
   - View user roles
   - Assign roles
   - Manage permissions

### User Roles

| Role | Permissions |
|------|-------------|
| Super Admin | Full system access |
| Admin | Administrative access, no system config |
| User | Standard user access |
| Viewer | Read-only access |

### Configuration Settings

**Client Configuration:**
- Automation pack settings
- Routing rules
- Notification preferences
- Integration credentials

**Workflow Configuration:**
- Enable/disable workflows
- Adjust schedules
- Configure thresholds
- Set retry policies

---

## Troubleshooting

### Common Issues

#### Issue: Leads Not Being Captured

**Possible Causes:**
- Webhook not configured
- Invalid client_id
- Missing required fields

**Solutions:**
1. Verify webhook URL is correct
2. Check client_id in request
3. Ensure email and source fields are present
4. Check error logs in Monitoring Dashboard

#### Issue: Documents Not Processing

**Possible Causes:**
- Unsupported file format
- File too large
- Storage full

**Solutions:**
1. Verify file format is supported
2. Check file size (<10MB recommended)
3. Check disk space in Monitoring Dashboard
4. Review document in Human Review Queue

#### Issue: Tasks Not Being Assigned

**Possible Causes:**
- No available team members
- Skills mismatch
- Workload at capacity

**Solutions:**
1. Check team member availability
2. Verify required skills are configured
3. Increase team member workload limits
4. Manually assign task

#### Issue: Alerts Not Received

**Possible Causes:**
- Email not configured
- Notification channels disabled
- Alert threshold not met

**Solutions:**
1. Verify email configuration
2. Check notification channel settings
3. Review alert rules and thresholds
4. Check spam folder

### Getting Help

**Self-Service:**
1. Check this User Guide
2. Review FAQ section
3. Check Monitoring Dashboard for errors
4. Review system logs

**Contact Support:**
- Email: support@automation-platform.com
- Phone: 1-800-SUPPORT (business hours)
- Emergency: emergency@automation-platform.com (24/7)

---

## FAQ

### General Questions

**Q: How do I add a new team member?**

A: Navigate to Settings > Team Members > Add New. Enter their information and assign appropriate roles.

**Q: Can I customize the automation workflows?**

A: Yes, administrators can customize workflows through the n8n interface. Contact your administrator for access.

**Q: How long is data retained?**

A: 
- Documents: 90 days
- Logs: 30 days
- Backups: 30 days
- Reports: 180 days

**Q: Is my data secure?**

A: Yes, all sensitive data is encrypted at rest using AES-256 encryption. Credentials are stored encrypted in the database.

### Lead Management

**Q: Why is my lead marked as duplicate?**

A: The system detected another lead with the same email address for your client. Duplicates are flagged to prevent redundant processing.

**Q: Can I manually adjust lead scores?**

A: Lead scores are automatically calculated. However, administrators can adjust scoring rules in the workflow configuration.

**Q: How do I export leads?**

A: Navigate to Leads section, apply any filters, and click "Export to CSV" button.

### Document Processing

**Q: What file formats are supported?**

A: PDF, JPG, PNG, DOC, DOCX, XLS, XLSX, TXT. Maximum file size is 10MB.

**Q: How accurate is the data extraction?**

A: Accuracy varies by document type and quality. Typical accuracy is 85-95%. Low-confidence extractions are sent to human review.

**Q: Can I reprocess a document?**

A: Yes, administrators can trigger reprocessing through the n8n interface.

### Task Management

**Q: How are tasks prioritized?**

A: Tasks are prioritized based on: 1) Priority level, 2) Due date, 3) Creation date.

**Q: Can I reassign a task?**

A: Yes, click on the task and select "Reassign" to choose a different team member.

**Q: What happens when a task is overdue?**

A: Overdue tasks trigger alerts, appear in the overdue list, and may escalate to management based on configuration.

### Monitoring & Alerts

**Q: How often are metrics updated?**

A: Metrics are collected every 5 minutes. Dashboards auto-refresh every 30 seconds.

**Q: Can I customize alert thresholds?**

A: Yes, administrators can adjust alert thresholds in the workflow configuration.

**Q: How do I acknowledge an alert?**

A: Click on the alert in the Monitoring Dashboard and click "Acknowledge" button.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + /` | Open search |
| `Ctrl + H` | Go to home |
| `Ctrl + L` | Go to leads |
| `Ctrl + D` | Go to documents |
| `Ctrl + T` | Go to tasks |
| `Ctrl + M` | Go to monitoring |
| `Esc` | Close modal/dialog |

---

## Best Practices

### Lead Management
1. Review new leads daily
2. Follow up on high-score leads within 24 hours
3. Keep lead data up-to-date
4. Monitor duplicate detection

### Document Processing
1. Use clear, high-quality scans
2. Review low-confidence extractions promptly
3. Provide feedback on classification accuracy
4. Keep review queue under 50 items

### Task Management
1. Update task status regularly
2. Complete tasks before due date
3. Add notes for context
4. Communicate delays early

### Monitoring
1. Check dashboard daily
2. Acknowledge alerts promptly
3. Review error logs weekly
4. Monitor SLA compliance

---

## Glossary

**Terms:**
- **Client** - Organization using the automation platform
- **Pack** - Collection of related automation workflows
- **Workflow** - Automated process for specific task
- **DLQ** - Dead Letter Queue (failed operations)
- **SLA** - Service Level Agreement (time commitment)
- **Enrichment** - Adding additional data to records
- **Routing** - Sending data to destination systems

---

## Support Resources

**Documentation:**
- System Architecture: Technical system overview
- Operations Manual: System administration guide
- API Documentation: Developer reference
- Deployment Guide: Installation instructions

**Training:**
- Video tutorials (coming soon)
- Webinars (monthly)
- One-on-one training (available on request)

**Community:**
- User forum: forum.automation-platform.com
- Knowledge base: kb.automation-platform.com
- Blog: blog.automation-platform.com

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-29  
**Maintained By:** Documentation Team
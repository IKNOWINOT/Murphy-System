# Quick Reference - Option C Systems

## Commands

### Librarian Commands
```
/librarian start                          - Begin discovery workflow
/librarian interpret <command>            - Explain command in natural language
/librarian natural <command>             - Convert command to natural language
```

### Hybrid Commands
```
/swarm <role> #context                    - Generate AI agent swarm
/analyze <target> #context                - Analyze target
/plan <objective> #context                - Create plan
/campaign <name> #context                 - Launch marketing campaign
/content <topic> #context                 - Create content
/lead <action> #context                   - Manage leads
/proposal <type> #context                 - Generate proposal
/budget <type> #context                   - Manage budget
/deploy <target> #context                 - Deploy system
/test <scope> #context                    - Run tests
/approve <request> #context               - Approve request
```

### Workflow Commands
```
/workflow execute executive_planning      - Execute executive planning workflow
/workflow execute sales_pipeline          - Execute sales pipeline workflow
/workflow execute marketing_campaign      - Execute marketing campaign workflow
/workflow execute software_development    - Execute software development workflow
```

### Builder Commands
```
/command build                            - Open command builder dropdown
```

---

## API Endpoints

### Enhanced Librarian
```
POST /api/librarian/enhanced              - Discovery workflow
POST /api/librarian/interpret             - Command interpretation
POST /api/librarian/natural-to-command    - Natural to command
```

### Executive Bots
```
GET  /api/executive/bots                  - List all bots
POST /api/executive/execute               - Execute bot command
POST /api/executive/workflow/<name>       - Execute workflow
GET  /api/executive/terminology/<role>    - Get bot terminology
```

### Hybrid Commands
```
POST /api/commands/parse                  - Parse command
GET  /api/commands/dropdown-data          - Get dropdown data
GET  /api/commands/workflows              - List workflows
POST /api/commands/validate               - Validate syntax
```

---

## Bot Roles

### Executive Bots
- **CEO** - Business strategy, executive decisions
- **CTO** - Technical architecture, technology decisions
- **CFO** - Financial planning, budget management

### Management Bots
- **VP Engineering** - Engineering team, development process
- **VP Product** - Product strategy, feature roadmap
- **VP Sales** - Sales strategy, revenue targets
- **VP Marketing** - Marketing strategy, campaign execution

### Individual Contributor Bots
- **Software Engineer** - Implementation, code quality
- **QA Engineer** - Testing, quality assurance
- **Content Manager** - Content creation, SEO
- **Account Executive** - Lead qualification, closing deals

---

## Domains

### Executive
- Terminology: market share, competitive advantage, strategic vision
- Bots: CEO, CTO, CFO
- Gates: Executive approval, strategic alignment

### Technology
- Terminology: technical architecture, scalability, microservices
- Bots: CTO, Software Engineer
- Gates: Technical Architecture Review, Security Compliance

### Engineering
- Terminology: API design, CI/CD, code review
- Bots: VP Engineering, Software Engineer, QA Engineer
- Gates: Performance Benchmark, User Acceptance Testing

### Marketing
- Terminology: campaign strategy, content calendar, SEO
- Bots: VP Marketing, Content Manager
- Gates: Campaign Approval, Brand Compliance, Content Quality

### Sales
- Terminology: sales process, lead scoring, proposal automation
- Bots: VP Sales, Account Executive
- Gates: Lead Qualification, Proposal Approval, Contract Review

### Finance
- Terminology: budget, revenue, ROI, EBITDA
- Bots: CFO
- Gates: Budget Approval, Revenue Recognition, Financial Reporting

---

## Workflows

### Executive Planning
**Sequence:** CEO → CTO → CFO → CEO
**Commands:**
```
/plan strategy #quarterly business objectives,
/plan architecture #technical roadmap,
/budget plan #resource allocation,
/approve executive #final plan
```

### Sales Pipeline
**Sequence:** Account Executive → VP Sales → CFO → Account Executive
**Commands:**
```
/lead qualify #enterprise prospect,
/proposal generate #custom solution,
/review pricing #deal terms,
/contract create #master agreement,
/approve sales #final deal
```

### Marketing Campaign
**Sequence:** VP Marketing → Content Manager → VP Marketing → CFO → VP Marketing
**Commands:**
```
/campaign plan #Q4 launch,
/content create #marketing materials,
/analyze metrics #target audience,
/budget allocate #campaign spend,
/approve marketing #go live
```

### Software Development
**Sequence:** VP Engineering → Software Engineer → QA Engineer → VP Engineering → CTO
**Commands:**
```
/swarm generate SoftwareEngineer #implement feature,
/analyze code #security review,
/test automated #QA suite,
/deploy staging #feature test,
/approve technical #production release
```

---

## Example Commands

### Discovery
```
"I need to automate my software company"
"Create a complete business automation system"
"Generate gates and workflows for my business"
```

### Natural Language to Command
```
Input: "Create a team of engineers to build authentication"
Output: /swarm Engineer #build authentication

Input: "Analyze the code for security issues"
Output: /analyze code #security review

Input: "Launch a Q4 marketing campaign"
Output: /campaign launch #Q4 initiative
```

### Command Interpretation
```
Input: /swarm generate SeniorEngineer #implement auth system
Output: This command creates a swarm of AI agents led by a Senior Engineer
        to implement an authentication system, using domain terminology
        from the engineering domain.

Input: /campaign launch #Q4 product launch
Output: VP Marketing should launch a marketing campaign as specified
        with goal: Q4 product launch
```

---

## Quick Start

### 1. Start Discovery
```
/librarian start
```

### 2. Follow the Questions
Answer the librarian's questions about your business type, org structure, and documents.

### 3. Execute Commands
Once system is ready, execute commands like:
```
/swarm generate SeniorEngineer #full implementation
/campaign launch #Q4 initiative
/workflow execute executive_planning
```

### 4. Interpret Commands
Don't understand a command? Ask the librarian:
```
/librarian interpret /swarm generate Engineer #build feature
```

### 5. Build Commands Interactively
Use the command builder:
```
/command build
```

---

## Tips

- **Use # for context**: Always add a comment after # to provide context
- **Chain commands**: Use commas to chain multiple commands
- **Check interpretation**: Use `/librarian interpret` before executing complex commands
- **Use workflows**: For multi-step processes, use pre-built workflows
- **Review terminology**: Check bot terminology with `/api/executive/terminology/<role>`
- **Validate syntax**: Use `/api/commands/validate` before executing

---

## Common Patterns

### Software Development
```
/swarm generate SeniorEngineer #implement feature,
/analyze code #security review,
/test automated #QA suite,
/deploy production #version 2.1
```

### Marketing Campaign
```
/campaign plan #Q4 launch,
/content create #marketing materials,
/analyze metrics #target audience,
/budget allocate #campaign spend
```

### Sales Deal
```
/lead qualify #enterprise prospect,
/proposal generate #custom solution,
/review pricing #deal terms,
/contract create #master agreement
```

### Executive Planning
```
/plan strategy #quarterly objectives,
/plan architecture #technical roadmap,
/budget plan #resource allocation
```

---

## Error Messages

### "Bot not found"
**Cause:** Invalid bot role name  
**Fix:** Check `/api/executive/bots` for valid bot roles

### "Invalid command format"
**Cause:** Command doesn't start with /  
**Fix:** Add / at the beginning of command

### "No context provided"
**Cause:** Missing #comment in command  
**Fix:** Add #context to provide clarity

### "Workflow not found"
**Cause:** Invalid workflow name  
**Fix:** Check `/api/commands/workflows` for valid workflows

---

## Status Codes

- **200** - Success
- **400** - Bad request (missing parameters)
- **404** - Not found (invalid endpoint or resource)
- **500** - Server error (check logs)

---

## File Locations

- `enhanced_librarian_system.py` - Core librarian system
- `executive_bot_system.py` - Executive bots
- `hybrid_command_system.py` - Command system
- `enhanced_librarian_ui.js` - Frontend UI
- `murphy_backend_complete.py` - Backend (modify to integrate)
- `murphy_complete_v2.html` - Frontend (modify to integrate)

---

**Last Updated:** Implementation complete, ready for backend integration
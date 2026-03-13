---
name: QuestLog issue template custom
about: Template to keep QuestLog issues the same format
title: ''
labels: ''
assignees: ''

---

# Feature Request

## User Story
**Starter:**  
_As a software engineer, I need to... so that..._

**Description:**  
Describe the feature from the perspective of the user or developer who needs it.

Example:
> As a software engineer, I need the application to support separate databases for development, testing, and production so that environments remain isolated and production data is protected.

---

## Acceptance Criteria
**Starter:**  
The feature is considered complete when the following conditions are met:

- [ ] Condition 1
- [ ] Condition 2
- [ ] Condition 3

Example:
- [ ] Development environment uses the development database
- [ ] Test environment uses a separate test database
- [ ] Production environment uses the production database
- [ ] Environment selection is controlled via configuration or environment variables

---

## Technical Notes
**Starter:**  
Implementation considerations, constraints, or design details.

Include things like:

- Relevant frameworks or libraries
- Configuration changes
- Database schema considerations
- Environment variables
- Security considerations
- Migration steps

Example:
- Django `DATABASES` setting should support multiple environments
- Use environment variables to select the environment
- Avoid committing database credentials to source control

---

## Definition of Done
**Starter:**  
This issue is complete when:

- [ ] Code is implemented
- [ ] Feature works as expected
- [ ] Unit tests added or updated
- [ ] Existing tests pass
- [ ] Code reviewed and approved
- [ ] Documentation updated if needed
- [ ] Changes merged into main branch

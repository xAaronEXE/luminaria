# Public terms and privacy pages

Published on the personal Luminaria identity Worker, version `4ffb51ee-9382-45c1-a3f9-ee93cb12126c`:

- https://luminaria-identity.dessellesoftwaresolutions.workers.dev/terms
- https://luminaria-identity.dessellesoftwaresolutions.workers.dev/privacy

Aliases `/terms-of-service` and `/privacy-policy` also work. Public contact is `dessellebusiness@gmail.com`, selected by the user before publication. The earlier personal contact was never published by this deployment.

Content reflects the reviewed implementation: provider identity data and limited OAuth scopes, Windows-protected desktop credentials and hashed server sessions, offline grace/revocation limitations, local-versus-remote tool processing, optional aggregate-only Insights sync, 730-day Insights retention, account records retained until removed, and verified privacy requests handled through the contact email. No in-app account-deletion feature or universal offline guarantee is claimed. The terms do not invent a business entity, jurisdiction, arbitration requirement, subscription or payment policy. Publication is not a legal-compliance certification.

Public routes require no account/database access and use static server-rendered HTML with no scripts, trackers, forms or external assets. Tests cover GET/HEAD, route aliases, no account DB access, no cookies, headers, revision date and the correct business contact. Existing mocked provider and release suites also pass after declaring the additional Worker module in their Miniflare configuration.

Live verification: GET and HEAD returned 200 for both primary URLs; content is HTML, includes the business contact, excludes the old personal email and sets no cookie. `/health` remains healthy and all three providers are configured. Provider dashboard policy fields and fresh Google/GitHub/Discord login acceptance still require user completion; publishing these pages does not update those dashboard fields automatically.

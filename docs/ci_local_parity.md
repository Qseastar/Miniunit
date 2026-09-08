# CI and local parity

All P2g tests, tools, and reports are offline. CI validates structured course-chunk metadata; it does not require, upload, or inspect local PDF binaries. Local WSL may contain approved source PDFs for a human visual evidence review, which CI must explicitly not claim to perform.

No command reads `.env`, an API key, or localhost. Reports contain public template metadata, not learner state or credentials. Paths are repository-relative, avoiding Windows/WSL user-directory assumptions. A green CI run means schema, metadata, scoring, isolation, and regression checks passed; it does not replace content-owner approval or visual review of pages.

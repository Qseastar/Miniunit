# Learner-state privacy boundary

This local MVP stores an anonymous UUID, course concept IDs, mastery values,
misconception identifiers, compact reviewed-verification metadata, and
timestamps/schema versions.

It does not store names, email, student IDs, IP addresses, device fingerprints,
browser history, complete learner questions, complete learner answers, LLM
answers, prompts, course text, API keys, Authorization headers, or `.env`
contents. The UUID is not an account or authentication mechanism. A copied
localhost URL can access the same local profile, so this design is appropriate
only for the stated single-machine MVP boundary.

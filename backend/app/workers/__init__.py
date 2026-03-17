"""Background workers for Seabay V1.5.

Workers run as async tasks during application lifespan.
They handle:
- Task delivery retries
- TTL expiration (tasks, intents, introductions)
- Agent status decay (online → away → offline)
- Relationship strength re-derivation
"""

# Full access mode

Settings > Tools & permissions > Access mode selects Review actions or Full access.
The selected mode is persisted per profile; the effective mode is latched when the
backend starts. Saving a different mode requires a complete app restart in either
direction. Review actions remains the default.

Full access exposes configured execution and MCP tools and assigns automatic
execution to new tool calls, including writes, deletes, network requests, durable
memory and scheduled actions. It does not install connectors, supply credentials,
grant OS permissions or remove the file tools' workspace boundary. Shell tools can
access outside that boundary under the current Windows user's permissions.

Previously queued approvals retain their stored tier and require a decision.
Denied actions are not retried automatically. Tool outputs and actions remain logged.

Validation: isolated Python processes verified review/full catalogs, MCP inclusion,
prompt descriptions, unchanged effective permissions after saving, and activation
of the saved mode in a fresh process. Python compilation and frontend JavaScript
syntax checks passed. No full-access actions were run on the user's data.

The source backend must be restarted to load this feature; the installed desktop
executable must be rebuilt before it includes these changes.

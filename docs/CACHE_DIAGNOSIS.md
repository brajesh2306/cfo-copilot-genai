# Puzzle 2 — initial diagnosis (written before implementation changes)

## Evidence from the supplied request log

- The log contains 220 requests.
- `cached_tokens` is 16 for 219 requests and 0 for one request. The average cached tokens are approximately 15.93, while the average prompt length is approximately 455 tokens.
- The `system_instructions` segment embeds a request-specific timestamp and request ID near the beginning of the prompt. This makes the earliest prefix diverge between requests.
- Variable user profile, retrieved context, conversation history, and query are also assembled into the prompt. These should remain after a stable shared prefix rather than being interleaved with static instructions.
- The logged serving engine reports prefix caching enabled with a block size of 16 tokens. The repeated 16-token cache count is consistent with only the first block being reusable, not with effective long-prefix reuse.

## Hypotheses to verify with a controlled benchmark

1. Dynamic fields near the start of the prompt are the primary cause of low prefix reuse.
2. Stable system policy and tool schemas are not kept as a long, identical prefix across requests.
3. Tenant/session-specific content must not be made globally reusable merely to improve cache hit rate; cache keys and reuse boundaries must preserve tenant isolation.

This is a log-based diagnosis, not a measured proof of the fix. The final benchmark must compare cache on/off and record TTFT, tokens/second, hit rate, and memory at 1, 4, and 16 concurrent sessions.

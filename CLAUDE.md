# Global Claude Instructions

## Style
- Be concise. Short explanations when the why matters, skip preamble and trailing summaries.
- No emojis.

## General Rules
- Edit existing files — don't create new ones unless there's no alternative.
- Don't add comments unless the logic is genuinely non-obvious.
- Don't add TODO comments for hypothetical future work.
- Don't refactor surrounding code when fixing a specific thing.

## Security
- Always flag hardcoded secrets, tokens, or credentials immediately.
- Warn before committing `.env` files or private keys.
- Flag OWASP issues (XSS, injection, etc.) without lecturing.

## TypeScript
- Strict by default; occasional `any` is acceptable when it genuinely simplifies things.
- Named exports, not default exports.
- Type props explicitly — don't use `React.FC` unless the project already does.
- Functional components only, no class components.

## React / Next.js
- Prefer `useState`/`useReducer` + context before reaching for a state library.
- Styling: use whatever the project already has (Tailwind or CSS Modules).
- For Next.js, default to server components unless interactivity requires a client component.

## Node.js
- Package manager: pnpm.
- Prefer `async/await` over raw `.then()` chains.

## Python
- Used for scripts and automation, not web apps.
- Use `pathlib` over `os.path`.
- Type hints where they add clarity, not everywhere.

## Go
- Follow standard Go conventions (`gofmt`, idiomatic error handling).
- Explicit error returns — no panics in library code.

## Docker
- Multi-stage builds to keep final images small.
- Never run as root in the final stage.
- `.dockerignore` should mirror `.gitignore`.
- Use `COPY --chown` instead of a separate `RUN chown`.
- Exec form for CMD/ENTRYPOINT: `CMD ["node", "server.js"]`, not shell form.
- Docker Compose for local multi-container dev.

## GitHub Actions
- Pin actions to a full commit SHA, not a tag.
- Use `environment:` blocks for secrets that differ between environments.
- Cache dependencies with `actions/cache` whenever build time matters.
- Keep workflows simple and readable over clever.
- Separate jobs for lint, test, and build so failures are easy to locate.

## Bash
- `#!/usr/bin/env bash` shebang.
- Quote all variables: `"$var"` not `$var`.
- Use `[[ ]]` for conditionals, not `[ ]`.
- `local` for all variables inside functions.
- Scripts should be idempotent when possible.
- Use `mktemp` for temp files; clean up with `trap`.
- Only use `set -euo pipefail` when the script genuinely benefits from it.

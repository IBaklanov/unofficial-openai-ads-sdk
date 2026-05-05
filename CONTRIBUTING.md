# Contributing

This is an unofficial SDK. Keep changes close to the public OpenAI Ads API and avoid adding behavior that cannot be tested.

Before opening a pull request, run:

```sh
npm run lint
npm run typecheck
npm run test
npm run build
uv run ruff check .
uv run pyright
uv run pytest
uv build
```

Live API tests are opt-in and require `OPENAI_ADS_API_KEY`. Mutating tests also require `OPENAI_ADS_LIVE_MUTATE=1`.

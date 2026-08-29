# Prompting guide

Turn the user's request into a compact production specification. Preserve a detailed user prompt instead of embellishing it. Add only information that materially improves a vague request.

Use the relevant lines:

```text
Intended use: <where the image will appear>
Primary request: <subject and action>
Scene/background: <setting>
Style/medium: <photo, illustration, 3D, etc.>
Composition: <framing, camera angle, subject placement, useful negative space>
Lighting/mood: <light and atmosphere>
Text (verbatim): "<exact visible text>"
Constraints: <must keep or must include>
Avoid: <unwanted content, logos, watermark>
```

## Generation

- Put the scene and main subject before secondary detail.
- State intended use and aspect ratio so composition fits the destination.
- Quote exact visible text. Do not invent copy, brands, characters, or narrative details.
- Use `--n` for variants of one prompt; use batch jobs for distinct assets.

## Editing

- Number every input image and state its role.
- Describe the requested change first, then repeat invariants: `change only X; keep Y and Z unchanged`.
- Keep identity, geometry, pose, layout, text, or lighting locked when the user requires it.
- Treat masks and natural-language editing as guided generation, not pixel-perfect deterministic editing.

## Iteration

Inspect the result before accepting it. On each retry, change one issue at a time and repeat all invariants to reduce drift.

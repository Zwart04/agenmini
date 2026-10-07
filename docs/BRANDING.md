# Agen Mini mascot

The app mascot is a transparent cutout adapted from the owner's supplied PNG.
Background extraction and edge cleanup used the built-in imagegen tool.
The app consumes `frontend/mascot.png`; no full-page background is included.
The working animation is a CSS transform on the client, disabled for reduced
motion. No video decoder, animation server or new VPS process is required.

Prompt 1: Extract only the white cat-like robotic mascot with dark charcoal
scarf/body and oval eyes; preserve design, pose, proportions and colors.
Remove the photographic rectangle, glow, shadows, noisy edges and stray pixels.
Use a genuinely transparent background and modest transparent padding.

Prompt 2: Clean up the exact cutout. Keep character design, pose, colors and
connected shapes unchanged. Remove isolated specks and noisy halos, especially
the floating white blob between the ears. Preserve smooth antialiased edges.

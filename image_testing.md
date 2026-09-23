## TEST AGENT PROMPT – IMAGE INTEGRATION RULES ##
- Always use base64-encoded images for all tests and requests. Accepted formats: JPEG, PNG, WEBP only.
- Do not upload blank, solid-color, or uniform-variance images — every image must contain real visual features (objects, edges, textures, shadows).
- If the image is not PNG/JPEG/WEBP, transcode it before upload; re-detect MIME after transformations.
- Animated images: extract first frame only. Resize large images to reasonable bounds.

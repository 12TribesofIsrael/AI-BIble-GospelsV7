# Templates

JSON2Video project templates that define the visual layout, scene structure, and element types for rendered videos.

## Files

| Template | Version | Description |
|---|---|---|
| `v7-ken-burns.json` | v7.2 (production) | 20 scenes with Ken Burns zoom/pan effects on static FLUX images. Template ID: `h5yD4ZbxhCPNFQ2WoVUs` |
| `v8-kling.json` | v8.0 (testing) | 20 scenes with Kling AI video elements. Includes `loop: -1` and `duration: -2` on all video elements. Template ID: `cHtpubYegDm2patG2tym` |

## Template Variables

Each template expects these variables per scene (1-20):

| Variable | Type | Description |
|---|---|---|
| `sceneN_videoUrl` | string | URL to the video/image file for scene N |
| `sceneN_voiceOverText` | string | Biblical text for ElevenLabs narration |
| `sceneN_overlaidText` | string | Short text overlay (3-8 words) |

## How Templates Work

1. Templates are created/edited in the [JSON2Video dashboard](https://json2video.com)
2. The n8n workflow sends template variables via the JSON2Video API
3. JSON2Video substitutes `{{variableName}}` placeholders with actual values
4. The rendered MP4 is returned via a download URL

## Important Notes

- Template IDs change when you save a new version in the JSON2Video dashboard
- Always update the template ID in the n8n workflow after modifying a template
- Master backups of templates are in `../backups/templates/` — never edit those

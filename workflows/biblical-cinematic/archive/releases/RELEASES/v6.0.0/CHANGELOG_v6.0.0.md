# 📝 Changelog - v6.0.0

**Release Date**: February 5, 2026  
**Version**: 6.0.0 - Master Production Release

---

## 🚀 Major Changes

### **Workflow Consolidation**
- ✅ **NEW**: Official master production workflow consolidated from working v3 prototype
- ✅ **Renamed**: `BibleWorkflowv3_20 Scene` → `Biblical-Video-Workflow-v6.0.0`
- ✅ **Status**: Production-ready with verified working configuration
- ✅ **Location**: `N8N/RELEASES/v6.0.0/Biblical-Video-Workflow-v6.0.0.json`

### **API Model Updates**
- ✅ **Perplexity AI**: Updated to `sonar-pro` (from deprecated `llama-3.1-sonar-large-128k-online`)
- ✅ **Model Version**: Latest supported Perplexity chat completion model
- ✅ **Compatibility**: Verified working as of February 2026

### **Voice Configuration**
- ✅ **ElevenLabs Voice ID**: `NgBYGKDDq2Z8Hnhatgma` (mature narrator)
- ✅ **Speed**: 0.9x for natural biblical pacing
- ✅ **Model**: `elevenlabs` with connection ID `my-elevenlabs-connection`

---

## ✨ New Features

### **Biblical Content Processing**
- ✅ Enhanced Black Hebrew Israelite visual representation prompts
- ✅ Mandatory character depiction guidelines (deeply melanated skin, natural hair, traditional garments)
- ✅ 20-scene architecture for full-length biblical videos
- ✅ Exact biblical text preservation (word-for-word, line-by-line)

### **Cinematic Motion Effects**
- ✅ Ken Burns effects with 5 motion types: `zoom-in`, `zoom-out`, `ken-burns`, `pan-right`, `pan-left`
- ✅ Dynamic zoom parameters: -10 to 10 range
- ✅ Pan directions: `center`, `left`, `right`
- ✅ Smooth transitions with `ease-in-out` easing
- ✅ Scene-specific animation cycling (varies per scene for visual variety)

### **Template Variables**
- ✅ 20 scenes × 7 variables per scene = 140+ dynamic variables
- ✅ Global motion settings: `globalAnimation`, `motionSmoothing`, `cinematicMode`
- ✅ Auto-calculated scene duration based on voice-over length
- ✅ Debug info with version tracking (`Template Variables v6.2 - Ken Burns Effect Fixed`)

---

## 🔧 Improvements

### **Workflow Architecture**
- ✅ **Node Chain**: Start → Text Input → Prompt Builder → AI Scene Generator → Template Formatter → Video Generator → Status Loop → Output
- ✅ **Status Checking**: 15-second intervals with smart routing (Video Complete / Video Error / Still Processing)
- ✅ **Error Handling**: Dedicated error output node with timestamp and detailed messages
- ✅ **Polling System**: Automatic retry until video completion or error

### **Code Quality**
- ✅ JSON parsing with regex fallback for Perplexity AI responses
- ✅ Text cleaning function removes unsafe characters for JSON safety
- ✅ Scene validation ensures 20 scenes minimum (throws error if empty)
- ✅ Template variable validation with debug output

### **JSON2Video Integration**
- ✅ Template ID: `G5BGObQCF6meMAZG7F0g` (verified working)
- ✅ Resolution: HD (1920×1080)
- ✅ Quality: High
- ✅ Settings: `sceneDuration: "auto"`, `voiceTiming: "natural"`

---

## 🐛 Bug Fixes

### **Model Deprecation**
- ✅ **FIXED**: `Invalid model 'llama-3.1-sonar-large-128k-online'` error
- ✅ **Solution**: Migrated to `sonar-pro` as per Perplexity documentation
- ✅ **Verification**: Model tested and working as of February 2026

### **Ken Burns Effect**
- ✅ **Version**: `Template Variables v6.2 - Ken Burns Effect Fixed`
- ✅ **Issue**: Previous versions may have had inconsistent motion parameters
- ✅ **Fix**: Standardized zoom/pan values for JSON2Video API compatibility

---

## 📋 Breaking Changes

### **Model Name**
- ⚠️ **Deprecated**: `llama-3.1-sonar-large-128k-online`
- ✅ **New**: `sonar-pro`
- **Impact**: Workflows using old model will fail with `Invalid model` error
- **Migration**: Update model name in "Biblical Content Prompt Builder" node

### **Version Numbering**
- Previous versions: v5.1.1 and earlier
- New version: v6.0.0 (major version bump for master release consolidation)

---

## 🗂️ File Structure Changes

### **New Files**
```
N8N/RELEASES/v6.0.0/
├── Biblical-Video-Workflow-v6.0.0.json  (Master workflow)
├── RELEASE_NOTES_v6.0.0.md              (This release documentation)
└── CHANGELOG_v6.0.0.md                  (Detailed change log)
```

### **Updated References**
- `N8N/n8n/WorkFlows/BibleWorkflowv3_20 Scene.json` → Updated name to v6.0.0
- `N8N/RELEASES/v5.1.0/` and `v5.1.1/` → Previous versions (still available)

---

## 📊 Metrics

### **Code Changes**
- **Lines Modified**: 2 (workflow name update)
- **New Files**: 3 (workflow + 2 documentation files)
- **Total Nodes**: 10 (unchanged from v3)
- **Template Variables**: 140+ (20 scenes × 7 variables)

### **API Changes**
- **Perplexity Model**: 1 change (model name)
- **ElevenLabs**: No changes (already configured)
- **JSON2Video**: No changes (template ID stable)

---

## ✅ Testing Status

### **Verified Working**
- ✅ Perplexity AI scene generation (`sonar-pro` model)
- ✅ JSON2Video rendering (Template `G5BGObQCF6meMAZG7F0g`)
- ✅ ElevenLabs voice synthesis (Voice ID `NgBYGKDDq2Z8Hnhatgma`)
- ✅ Status polling and completion detection
- ✅ Error handling and retry logic

### **Test Cases**
- ✅ 20-scene biblical video generation
- ✅ Ken Burns motion effects
- ✅ Auto scene duration calculation
- ✅ Voice-over timing with natural pacing

---

## 🔄 Migration Guide

### **From v5.1.0 or v5.1.1**
1. Export your current workflow as backup
2. Import `Biblical-Video-Workflow-v6.0.0.json`
3. Update API credentials if needed (Perplexity, ElevenLabs, JSON2Video)
4. Verify template ID: `G5BGObQCF6meMAZG7F0g`
5. Test with sample biblical text

### **From Earlier Versions (v5.0.0 or older)**
1. Full workflow replacement recommended
2. Re-configure all API credentials
3. Update template variable structure if custom modifications exist
4. Review new 20-scene architecture

---

## 🎯 Recommended Workflow

1. **Pre-process Text**: Use `biblical_text_processor_v2.py` (v1.4.0) to normalize 1611 spellings
2. **Import Workflow**: Load `Biblical-Video-Workflow-v6.0.0.json` into n8n
3. **Configure APIs**: Ensure Perplexity, ElevenLabs, and JSON2Video credentials are set
4. **Test Run**: Use sample biblical text (e.g., Psalm 23)
5. **Production**: Process full chapters with confidence

---

## 📚 Related Documentation

- **Release Notes**: `N8N/RELEASES/v6.0.0/RELEASE_NOTES_v6.0.0.md`
- **Text Processor**: `N8N/-p/biblical_text_processorv2/README.md` (v1.4.0)
- **Installation**: `N8N/INSTALLATION_GUIDE.md`
- **Previous Release**: `N8N/RELEASES/v5.1.1/RELEASE_NOTES_v5.1.1.md`

---

## 🙏 Credits

- **Text Normalization**: 100+ 1611 spelling patterns curated from KJV text analysis
- **Voice Selection**: ElevenLabs mature narrator voice tested for biblical narration
- **Motion Effects**: Ken Burns cinematic techniques adapted for biblical storytelling

---

**Version 6.0.0** - Master Production Release  
**Status**: STABLE  
**Date**: February 5, 2026

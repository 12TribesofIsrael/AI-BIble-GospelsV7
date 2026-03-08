# 🎬 Release Notes - v6.0.0

**Release Date**: February 5, 2026  
**Version**: 6.0.0 - Production Master Release  
**Status**: ✅ STABLE - PRODUCTION READY

---

## 📋 Overview

Version 6.0.0 consolidates all working components into the official **master production workflow**. This release includes verified working configurations for Perplexity AI (sonar-pro model), ElevenLabs voice integration, JSON2Video rendering, and comprehensive KJV text normalization.

---

## ✨ What's New in v6.0.0

### **🔧 API Model Updates**
- ✅ **Perplexity AI**: Migrated from deprecated `llama-3.1-sonar-large-128k-online` to supported `sonar-pro` model
- ✅ **ElevenLabs Voice**: Mature narrator voice `NgBYGKDDq2Z8Hnhatgma` (default)
- ✅ **JSON2Video**: Template-based rendering with Ken Burns motion effects

### **📖 Biblical Text Processing**
- ✅ **100+ 1611 Spelling Normalizations**: Comprehensive OCR/archaic spelling fixes for clean narration
- ✅ **KJV Grammar Preserved**: `thou/thee/thy/thine/ye/unto/shalt/hast/didst/art` remain intact
- ✅ **ElevenLabs-Optimized**: Zero pronunciation issues with TTS/auto-captions
- ✅ **Text Processor v1.4.0**: Integrated with optional AI sentence restructuring

### **🎥 Video Production**
- ✅ **20-Scene Architecture**: Full-length biblical video generation
- ✅ **Ken Burns Effects**: Professional cinematic motion (5 motion types cycling)
- ✅ **Template ID**: `G5BGObQCF6meMAZG7F0g`
- ✅ **Voice Integration**: Natural pacing at 0.9x speed

---

## 🗂️ Files in This Release

### **Workflows**
- `Biblical-Video-Workflow-v6.0.0.json` - Master production workflow (n8n)

### **Components**
- **Perplexity AI**: Scene generation (20 scenes)
- **JSON2Video**: Template-based video rendering
- **ElevenLabs**: Professional voice narration
- **Text Processor**: KJV normalization (separate tool)

---

## 📊 Technical Specifications

### **Workflow Architecture**
```
Input Text (KJV)
  ↓
Biblical Content Prompt Builder (sonar-pro)
  ↓
Perplexity AI Scene Generator (20 scenes)
  ↓
Enhanced Format for 16:9 Template (variables)
  ↓
Generate 16:9 Spiritual Video (JSON2Video)
  ↓
Status Check Loop (15s intervals)
  ↓
Final Video Output
```

### **API Models**
| Service | Model | Purpose |
|---------|-------|---------|
| Perplexity AI | `sonar-pro` | Scene generation |
| ElevenLabs | `elevenlabs` | Voice synthesis |
| JSON2Video | Template `G5BGObQCF6meMAZG7F0g` | Video rendering |

### **Voice Configuration**
- **Voice ID**: `NgBYGKDDq2Z8Hnhatgma` (mature narrator)
- **Speed**: 0.9x
- **Model**: ElevenLabs
- **Connection**: `my-elevenlabs-connection`

### **Video Output**
- **Resolution**: HD (1920×1080)
- **Quality**: High
- **Scenes**: Exactly 20
- **Duration**: Auto-calculated (typically 12-20 minutes)
- **Motion**: Ken Burns effects (zoom-in, zoom-out, pan-left, pan-right, ken-burns)

---

## 🔄 Migration from Previous Versions

### **From v5.1.0/v5.1.1**
- **Model Change**: Update Perplexity model from `llama-3.1-sonar-large-128k-online` → `sonar-pro`
- **Workflow**: Import `Biblical-Video-Workflow-v6.0.0.json`
- **No Template Changes**: Continue using existing JSON2Video template

### **From v5.0.0 or Earlier**
- Import full v6.0.0 workflow
- Update API credentials if needed
- Verify JSON2Video template ID: `G5BGObQCF6meMAZG7F0g`

---

## ✅ Verification Checklist

Before deploying v6.0.0:

- [ ] Perplexity API key configured
- [ ] Model set to `sonar-pro`
- [ ] ElevenLabs voice ID: `NgBYGKDDq2Z8Hnhatgma`
- [ ] JSON2Video template: `G5BGObQCF6meMAZG7F0g`
- [ ] Biblical text preprocessed with Text Processor v1.4.0 (optional but recommended)

---

## 🆕 Related Tools

### **Biblical Text Processor v1.4.0**
- **Location**: `N8N/-p/biblical_text_processorv2/`
- **Features**:
  - 100+ 1611 spelling normalizations
  - KJV grammar preservation
  - Optional AI sentence restructuring (OpenAI GPT-4o-mini)
  - Verse number removal
  - Multi-section support (1000-word chunks)

**Usage**:
```bash
cd N8N/-p/biblical_text_processorv2
python biblical_text_processor_v2.py
```

---

## 📚 Documentation

- **Installation Guide**: `N8N/INSTALLATION_GUIDE.md`
- **Text Processor**: `N8N/-p/biblical_text_processorv2/README.md`
- **Versioning Strategy**: `N8N/VERSIONING_STRATEGY.md`

---

## 🐛 Known Issues

None currently reported.

---

## 🎯 Production Recommendations

1. **Pre-process Text**: Use Text Processor v1.4.0 to normalize 1611 spellings before workflow input
2. **Voice Selection**: Default voice works well; alternatives listed in v5.1 README
3. **Scene Count**: Workflow enforces exactly 20 scenes; Perplexity AI distributes content intelligently
4. **Monitoring**: Status checks run every 15 seconds; typical render time 8-13 minutes

---

## 💡 Future Enhancements

- Additional voice profiles
- Multi-language support
- Alternative motion presets
- Batch processing support

---

## 📞 Support

For issues or questions:
- Review documentation in `N8N/DOCUMENTATION_INDEX.md`
- Check workflow logs for API errors
- Verify API credentials and quotas

---

**Version 6.0.0** - Master Production Release  
**Date**: February 5, 2026  
**Status**: STABLE

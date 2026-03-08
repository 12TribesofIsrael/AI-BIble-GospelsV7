# 📊 Version History - Biblical Video Production Platform

**Last Updated**: February 5, 2026

---

## 🎯 Current Production Version

### **Version 6.0.2** - Complete Fix Release
**Release Date**: February 18, 2026  
**Status**: ✅ STABLE - CURRENT PRODUCTION  
**Location**: `N8N/RELEASES/v6.0.2/`

**Key Files**:
- `Biblical-Video-Workflow-v6.0.2.json` - Fully fixed workflow
- `RELEASE_NOTES_v6.0.2.md` - Complete fix documentation
- `CHANGELOG_v6.0.2.md` - Detailed changelog

**Configuration**:
- **Perplexity AI**: `sonar-pro` (with enhanced JSON parsing)
- **ElevenLabs Voice**: `NgBYGKDDq2Z8Hnhatgma` (mature narrator)
- **JSON2Video Template**: `G5BGObQCF6meMAZG7F0g`
- **Scenes**: 20 (full production length)
- **Motion Effects**: Ken Burns (5 types with complete zoom/pan variables)
- **Text Processor**: v1.4.0 (KJV normalization)

**What's Fixed**:
- ✅ Enhanced JSON parsing (handles markdown code blocks from Perplexity)
- ✅ Complete Ken Burns variables (all zoomEnd/panEnd values set)
- ✅ No more JSON2Video 500 errors
- ✅ All 20 scenes render successfully

---

## 📚 Previous Versions

### **Version 6.0.1** - JSON Parsing Hotfix
**Release Date**: February 18, 2026  
**Status**: ⚠️ SUPERSEDED by v6.0.2  
**Location**: `N8N/RELEASES/v6.0.1/`

**Changes**:
- Enhanced JSON parsing for Perplexity AI responses
- Added markdown code block extraction (` ```json ... ``` `)
- Improved error messages with response preview

**Known Issues**:
- JSON2Video 500 errors on scenes with Ken Burns effects (fixed in v6.0.2)

---

### **Version 6.0.0** - Master Production Release
**Release Date**: February 5, 2026  
**Status**: ⚠️ SUPERSEDED by v6.0.2  
**Location**: `N8N/RELEASES/v6.0.0/`

**Features**:
- Official master workflow consolidation
- 20-scene architecture (full production)
- Ken Burns effects (5 motion types)
- Perplexity model: `sonar-pro`
- Text Processor v1.4.0 integration

**Known Issues**:
- JSON parsing failures with markdown-wrapped responses (fixed in v6.0.1)
- JSON2Video 500 errors (fixed in v6.0.2)

---

### **Version 5.1.1** - Perplexity Model Fix
**Release Date**: June 30, 2025  
**Status**: ⚠️ SUPERSEDED by v6.0.0  
**Location**: `N8N/RELEASES/v5.1.1/`

**Changes**:
- Updated Perplexity model from deprecated `llama-3.1-sonar-large-128k-online` to `sonar-pro`
- Documentation updates for model change

---

### **Version 5.1.0** - 20-Scene Production System
**Release Date**: June 28, 2025  
**Status**: ⚠️ SUPERSEDED by v6.0.0  
**Location**: `N8N/Version 5.1 - ElevenLabs 20-Scene Production/`

**Features**:
- 20-scene architecture (10x scale increase from v5.0.0)
- Intelligent content distribution via Perplexity AI
- Ken Burns effects cycling across all scenes
- 240+ template variables
- Production-ready long-form videos (12-20 minutes)

**Configuration**:
- Template ID: `YCEc18dUc0g8Dwd9DEBS`
- Voice ID: `6OzrBCQf8cjERkYgzSg8` (Young Jamal)
- Model: `llama-3.1-sonar-large-128k-online` (deprecated)

---

### **Version 5.0.0** - ElevenLabs Single Scene
**Release Date**: June 2025  
**Status**: ⚠️ LEGACY - Testing Framework  
**Location**: `N8N/Version 5 - ElevenLabs Single Scene/`

**Features**:
- ElevenLabs voice integration foundation
- Ken Burns effects (5 motion types)
- Professional captions
- 2-scene testing template
- Black Hebrew Israelite representation

**Configuration**:
- 2 scenes (testing/demo)
- ElevenLabs voice quality established
- Ken Burns animation syntax verified

---

### **Version 4.0.0 and Earlier**
**Status**: ⚠️ ARCHIVED  
**Location**: `N8N/Archive/Legacy_Workflows/`

Includes:
- Master_Long_Form.json
- Top_10_Videos.json
- Version 6 Archive

**Note**: These versions are preserved for historical reference but are no longer actively supported.

---

## 🔄 Version Migration Path

### **From v5.1.0 or v5.1.1 → v6.0.0**
1. Export current workflow as backup
2. Import `Biblical-Video-Workflow-v6.0.0.json`
3. Update API credentials (Perplexity, ElevenLabs, JSON2Video)
4. Verify template ID: `G5BGObQCF6meMAZG7F0g`
5. Test with sample biblical text

**Breaking Changes**:
- Perplexity model: `llama-3.1-sonar-large-128k-online` → `sonar-pro`
- Voice ID: `6OzrBCQf8cjERkYgzSg8` → `NgBYGKDDq2Z8Hnhatgma` (default)

### **From v5.0.0 or Earlier → v6.0.0**
- Full workflow replacement recommended
- Re-configure all API credentials
- Review 20-scene architecture (if coming from v5.0.0)
- Update template variable structure if custom modifications exist

---

## 📊 Version Comparison Matrix

| Feature | v6.0.0 | v6.0.1 | v6.0.2 | v5.1.1 | v5.1.0 | v5.0.0 |
|---------|--------|--------|--------|--------|--------|--------|
| **Status** | Superseded | Superseded | **CURRENT** | Superseded | Superseded | Legacy |
| **Scenes** | 20 | 20 | 20 | 20 | 20 | 2 |
| **Perplexity Model** | sonar-pro | sonar-pro | sonar-pro ✅ | sonar-pro | llama-3.1 (deprecated) | llama-3.1 (deprecated) |
| **JSON Parsing** | Basic | **Enhanced** ✅ | **Enhanced** ✅ | Basic | Basic | Basic |
| **Markdown Support** | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **zoomEnd Variables** | ❌ | ❌ | **✅ Complete** | ❌ | ❌ | ❌ |
| **panEnd Variables** | ❌ | ❌ | **✅ Complete** | ❌ | ❌ | ❌ |
| **JSON2Video 500 Errors** | ✅ Yes | ✅ Yes | **❌ Fixed** ✅ | ✅ Yes | ✅ Yes | Unknown |
| **Voice ID** | NgBYGKDDq2Z8Hnhatgma | NgBYGKDDq2Z8Hnhatgma | NgBYGKDDq2Z8Hnhatgma ✅ | 6OzrBCQf8cjERkYgzSg8 | 6OzrBCQf8cjERkYgzSg8 | NgBYGKDDq2Z8Hnhatgma |
| **Template ID** | G5BGObQCF6meMAZG7F0g | G5BGObQCF6meMAZG7F0g | G5BGObQCF6meMAZG7F0g ✅ | YCEc18dUc0g8Dwd9DEBS | YCEc18dUc0g8Dwd9DEBS | Various |
| **Motion Effects** | 5 types | 5 types | 5 types ✅ | 5 types | 5 types | 5 types |
| **Duration** | 12-20 min | 12-20 min | 12-20 min ✅ | 12-20 min | 12-20 min | 2-3 min |
| **Text Processor** | v1.4.0 | v1.4.0 | v1.4.0 ✅ | - | - | - |
| **KJV Normalization** | 100+ patterns | 100+ patterns | 100+ patterns ✅ | - | - | - |
| **Production Ready** | ⚠️ Partial | ⚠️ Partial | **✅ Yes** | ⚠️ Partial | ⚠️ Partial | ✅ Testing |

---

## 🎯 Recommended Actions

### **For New Users**
→ **Start with v6.0.2** - Latest stable release with all fixes

### **For v6.0.0 or v6.0.1 Users**
→ **Upgrade to v6.0.2** - Fixes critical JSON2Video 500 errors

### **For v5.x Users**
→ **Upgrade to v6.0.2** - Major improvements in stability and features

### **For Legacy Users**
→ **Migrate to v6.0.2** - Full system modernization

---

## 📞 Support Resources

### **Documentation**
- **v6.0.0 Release Notes**: `N8N/RELEASES/v6.0.0/RELEASE_NOTES_v6.0.0.md`
- **v6.0.0 README**: `N8N/RELEASES/v6.0.0/README.md`
- **Changelog**: `N8N/RELEASES/v6.0.0/CHANGELOG_v6.0.0.md`
- **Text Processor**: `N8N/-p/biblical_text_processorv2/README.md`

### **Version-Specific Guides**
- v5.1.0: `N8N/Version 5.1 - ElevenLabs 20-Scene Production/README.md`
- v5.0.0: `N8N/RELEASES/v5.0.0/RELEASE_NOTES_v5.0.0.md`

### **Master Documentation**
- **Documentation Index**: `N8N/DOCUMENTATION_INDEX.md`
- **Installation Guide**: `N8N/INSTALLATION_GUIDE.md`
- **Versioning Strategy**: `N8N/VERSIONING_STRATEGY.md`

---

## 🔮 Future Roadmap

### **Planned Versions**
- **v6.1.0**: Multi-narrator support, additional voice profiles
- **v6.2.0**: Custom motion preset library
- **v7.0.0**: Batch processing (multiple chapters)
- **v7.5.0**: Multi-language support (Spanish, Portuguese)
- **v8.0.0**: AI-generated background music

---

**Last Updated**: February 5, 2026  
**Current Version**: 6.0.0 - Master Production Release  
**Status**: STABLE ✅

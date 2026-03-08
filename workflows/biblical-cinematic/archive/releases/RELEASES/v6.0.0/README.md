# 🎬 **Version 6.0.0 - Master Production Release**

## 📊 **PRODUCTION STATUS: ✅ STABLE - MASTER RELEASE**

**Version**: 6.0.0  
**Release Date**: February 5, 2026  
**Based on**: Working BibleWorkflowv3 (20-Scene Production)  
**Status**: Master production workflow with all verified components  

---

## 🎯 **WHAT'S NEW IN v6.0.0**

### ✅ **Master Workflow Consolidation**
- **Official Production Workflow**: Consolidated from verified working v3 prototype
- **Perplexity AI Model**: Updated to `sonar-pro` (from deprecated `llama-3.1-sonar-large-128k-online`)
- **ElevenLabs Voice**: Mature narrator voice `NgBYGKDDq2Z8Hnhatgma` configured and tested
- **JSON2Video Template**: Template ID `G5BGObQCF6meMAZG7F0g` verified working
- **Ken Burns Effects**: Professional cinematic motion (5 motion types)

### ✅ **Biblical Text Processing Integration**
- **Text Processor v1.4.0**: Integrated KJV normalization tool
- **100+ 1611 Spellings**: Comprehensive archaic spelling fixes for clean narration
- **KJV Grammar Preserved**: `thou/thee/thy/thine/ye/unto/shalt/hast/didst/art` remain intact
- **ElevenLabs-Optimized**: Zero pronunciation issues with TTS/auto-captions
- **Optional AI Polish**: GPT-4o-mini sentence restructuring (10-22 words per sentence)

---

## 🔧 **CORE FEATURES - PRODUCTION READY**

### **Biblical Content Generation**
- **20-Scene Architecture**: Full production-length biblical videos
- **Black Hebrew Israelite Representation**: Mandatory visual guidelines for authentic cultural depiction
- **Exact Biblical Text**: Word-for-word preservation from input to narration
- **Intelligent Content Distribution**: Perplexity AI distributes content intelligently across 20 scenes

### **Voice & Audio**
- **Voice Model**: ElevenLabs (`NgBYGKDDq2Z8Hnhatgma` - mature narrator)
- **Speed**: 0.9x for natural biblical pacing
- **Auto-timing**: Natural voice synchronization
- **Connection**: `my-elevenlabs-connection`

### **Video Production**
- **Resolution**: Full HD (1920×1080)
- **Quality**: High (professional broadcast quality)
- **Duration**: Auto-calculated (typically 12-20 minutes)
- **Motion Effects**: Ken Burns animation (zoom-in, zoom-out, pan-left, pan-right, ken-burns)
- **Template**: JSON2Video Template `G5BGObQCF6meMAZG7F0g`

---

## 📂 **FILES IN THIS RELEASE**

### **Master Workflow**
```
N8N/RELEASES/v6.0.0/
├── Biblical-Video-Workflow-v6.0.0.json  ← Main production workflow
├── RELEASE_NOTES_v6.0.0.md              ← Comprehensive release notes
└── CHANGELOG_v6.0.0.md                  ← Detailed changelog
```

### **Related Tools**
- **Text Processor**: `N8N/-p/biblical_text_processorv2/biblical_text_processor_v2.py` (v1.4.0)
- **Text Processor README**: `N8N/-p/biblical_text_processorv2/README.md`

---

## ⚙️ **WORKFLOW ARCHITECTURE**

### **Node Flow**
```
Start Workflow
  ↓
Bible Chapter Text Input (KJV text)
  ↓
Biblical Content Prompt Builder (prepare request)
  ↓
Perplexity AI Scene Generator (sonar-pro → 20 scenes)
  ↓
Enhanced Format for 16:9 Template (variables + motion)
  ↓
Generate 16:9 Spiritual Video (JSON2Video API)
  ↓
Check Video Status (15-second polling)
  ↓
Video Status Router (Complete / Error / Still Processing)
  ↓
Final Video Output OR Error Output
```

### **10 Nodes Total**
1. **Start Workflow**: Manual trigger
2. **Bible Chapter Text Input**: Set variable with KJV text
3. **Biblical Content Prompt Builder**: JavaScript code to build Perplexity request
4. **Perplexity AI Scene Generator**: HTTP request to Perplexity API (`sonar-pro`)
5. **Enhanced Format for 16:9 Template**: JavaScript formatter with Ken Burns effects
6. **Generate 16:9 Spiritual Video**: HTTP POST to JSON2Video API
7. **Check Video Status**: HTTP GET status check
8. **Video Status Router**: Switch node (3 outputs)
9. **Final Video Output**: Success data extraction
10. **Error Output**: Error data extraction

---

## 🎥 **TECHNICAL SPECIFICATIONS**

### **API Configuration**
| Service | Model/ID | Purpose |
|---------|----------|---------|
| **Perplexity AI** | `sonar-pro` | Scene generation (20 scenes) |
| **ElevenLabs** | `NgBYGKDDq2Z8Hnhatgma` | Professional voice narration |
| **JSON2Video** | Template `G5BGObQCF6meMAZG7F0g` | Video rendering |

### **Ken Burns Motion System**
**5 Motion Types** (cycle through all 20 scenes):
- **zoom-in**: `zoomStart: 2`, `panStart: "center"`
- **zoom-out**: `zoomStart: -2`, `panStart: "center"`
- **ken-burns**: `zoomStart: 1`, `panStart: "left"`
- **pan-right**: `zoomStart: 0`, `panStart: "right"`
- **pan-left**: `zoomStart: 0`, `panStart: "left"`

**Animation Settings**:
- Duration: 8 seconds per scene
- Easing: `ease-in-out`
- Smoothing: High
- Mode: Professional cinematic

### **Template Variables** (140+ total)
Per scene (20 scenes × 7 variables):
- `scene{N}_overlaidText`: Caption text (3-8 words)
- `scene{N}_voiceOverText`: Full narration (20+ words)
- `scene{N}_imagePrompt`: AI image generation prompt
- `scene{N}_animation`: "ken-burns"
- `scene{N}_motionType`: One of 5 motion types
- `scene{N}_zoomStart`: -10 to 10
- `scene{N}_panStart`: "left", "center", or "right"

Global settings:
- `voiceModel`: "elevenlabs"
- `voiceID`: "NgBYGKDDq2Z8Hnhatgma"
- `globalAnimation`: "enabled"
- `motionSmoothing`: "high"
- `cinematicMode`: "professional"

---

## 🚀 **DEPLOYMENT INSTRUCTIONS**

### **Step 1: Import Workflow**
```bash
# In n8n UI:
1. Go to Workflows → Import from File
2. Select: N8N/RELEASES/v6.0.0/Biblical-Video-Workflow-v6.0.0.json
3. Click "Import"
```

### **Step 2: Configure API Credentials**
Ensure the following credentials are set up in n8n:

**Perplexity API**:
- Credential type: Bearer Auth
- Bearer token: Your Perplexity API key

**JSON2Video**:
- Credential type: HTTP Header Auth
- Header name: `X-Project-Key`
- Header value: Your JSON2Video API key

**ElevenLabs** (optional if using direct API):
- Connection ID: `my-elevenlabs-connection`
- Voice ID: `NgBYGKDDq2Z8Hnhatgma`

### **Step 3: Verify Template ID**
Check that the JSON2Video template ID is correct:
```json
// In "Generate 16:9 Spiritual Video" node
"template": "G5BGObQCF6meMAZG7F0g"
```

### **Step 4: Test Run**
1. Open workflow
2. Click "Test Workflow"
3. Use sample text (e.g., Psalm 23) in the "Bible Chapter Text Input" node
4. Monitor execution (typically 15-45 minutes for full render)

---

## 📋 **PRE-PROCESSING BIBLICAL TEXT**

### **Recommended: Use Text Processor v1.4.0**

For best results, pre-process your KJV text before feeding it to the workflow:

```bash
cd N8N/-p/biblical_text_processorv2
python biblical_text_processor_v2.py
```

**What it does**:
- ✅ Removes verse numbers (`1And`, `2Blessed`, etc.)
- ✅ Fixes 100+ archaic 1611 spellings (`vp→up`, `vpon→upon`, `deliuer→deliver`)
- ✅ Preserves KJV grammar (`thou/thee/thy/thine/ye/unto/shalt/hast/didst/art`)
- ✅ Optional AI sentence restructuring (10-22 words per sentence)
- ✅ Output ready for ElevenLabs TTS with zero pronunciation issues

**Setup**:
```bash
pip install openai  # Optional for AI polish
set OPENAI_API_KEY=your_key_here  # Optional
```

**Input**: Place KJV text in `Input` file  
**Output**: Cleaned text in `Output` file → Copy to workflow

---

## 🎯 **PRODUCTION RECOMMENDATIONS**

### **Content Preparation**
1. **Use Text Processor**: Pre-process all biblical text with v1.4.0
2. **Check Length**: 1000-3000 words ideal for 20 scenes
3. **Verify Formatting**: Remove existing verse references and chapter headers

### **Voice Selection**
- **Default**: `NgBYGKDDq2Z8Hnhatgma` (mature narrator, well-tested)
- **Alternatives**: See v5.1 README for 12+ voice options
- **Speed**: 0.9x is optimal for biblical narration (don't change unless testing)

### **Scene Distribution**
- Workflow enforces exactly 20 scenes
- Perplexity AI distributes content intelligently
- Each scene gets 20+ words minimum for narration

### **Monitoring**
- Status checks run every 15 seconds
- Typical render time: 8-13 minutes for JSON2Video
- Total workflow time: 15-45 minutes (depends on Perplexity + JSON2Video)

---

## 🐛 **TROUBLESHOOTING**

### **Common Issues**

**Issue**: `Invalid model 'llama-3.1-sonar-large-128k-online'`  
**Fix**: You're using an old workflow. Update to v6.0.0 which uses `sonar-pro`.

**Issue**: Video stuck in "Still Processing"  
**Fix**: Normal for large videos. Wait up to 45 minutes. Check JSON2Video dashboard for actual status.

**Issue**: Voice sounds robotic or mispronounces words  
**Fix**: Pre-process text with Text Processor v1.4.0 to fix archaic spellings.

**Issue**: Less than 20 scenes generated  
**Fix**: This workflow is hard-coded to enforce 20 scenes. Check Perplexity API response in workflow execution logs.

**Issue**: Template ID error  
**Fix**: Verify template `G5BGObQCF6meMAZG7F0g` exists in your JSON2Video account. Upload if missing.

### **Success Verification**
- ✅ Perplexity generates exactly 20 scenes
- ✅ All 5 motion types cycle correctly
- ✅ ElevenLabs voice clear and natural
- ✅ Final video duration: 12-20 minutes (typical)
- ✅ All biblical text preserved word-for-word

---

## 🔄 **MIGRATION FROM PREVIOUS VERSIONS**

### **From v5.1.0 or v5.1.1**
1. Export your current workflow as backup
2. Import `Biblical-Video-Workflow-v6.0.0.json`
3. Re-configure API credentials (copy from old workflow)
4. Verify template ID matches
5. Test with sample text

**Key Changes**:
- Model updated: `sonar-pro` (from `llama-3.1-sonar-large-128k-online`)
- Voice ID default: `NgBYGKDDq2Z8Hnhatgma` (mature narrator)
- Workflow name: `Biblical-Video-Workflow-v6.0.0`

### **From v5.0.0 or Earlier**
- Full workflow replacement recommended
- Re-configure all API credentials from scratch
- Review new 20-scene architecture documentation

---

## 📚 **DOCUMENTATION INDEX**

### **Release Documentation**
- **Release Notes**: `N8N/RELEASES/v6.0.0/RELEASE_NOTES_v6.0.0.md`
- **Changelog**: `N8N/RELEASES/v6.0.0/CHANGELOG_v6.0.0.md`

### **Related Tools**
- **Text Processor**: `N8N/-p/biblical_text_processorv2/README.md` (v1.4.0)

### **Project Documentation**
- **Installation Guide**: `N8N/INSTALLATION_GUIDE.md`
- **Versioning Strategy**: `N8N/VERSIONING_STRATEGY.md`
- **Documentation Index**: `N8N/DOCUMENTATION_INDEX.md`

### **Previous Versions**
- **v5.1.0**: `N8N/Version 5.1 - ElevenLabs 20-Scene Production/README.md`
- **v5.0.0**: `N8N/RELEASES/v5.0.0/RELEASE_NOTES_v5.0.0.md`

---

## 🎯 **FUTURE ROADMAP**

### **Planned Enhancements**
- **v6.1.0**: Additional voice profiles and multi-narrator support
- **v6.2.0**: Custom motion preset library
- **v7.0.0**: Batch processing support (multiple chapters)
- **v7.5.0**: Multi-language support (Spanish, Portuguese)
- **v8.0.0**: AI-generated background music integration

---

## 📞 **SUPPORT**

### **Resources**
- Documentation: `N8N/DOCUMENTATION_INDEX.md`
- Previous versions: `N8N/RELEASES/`
- Text processor: `N8N/-p/biblical_text_processorv2/`

### **Verification Checklist**
Before contacting support, verify:
- [ ] Perplexity API key configured (Bearer Auth)
- [ ] JSON2Video API key configured (HTTP Header Auth)
- [ ] Template ID correct: `G5BGObQCF6meMAZG7F0g`
- [ ] Voice ID correct: `NgBYGKDDq2Z8Hnhatgma`
- [ ] Model set to: `sonar-pro`
- [ ] Workflow imported: `Biblical-Video-Workflow-v6.0.0.json`

---

**🎉 Version 6.0.0 - Master Production Release - Ready for Professional Biblical Video Production!**
